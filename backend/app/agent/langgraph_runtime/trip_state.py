"""
Build a compact structured snapshot of everything already decided in the trip.

The day-planner and finalizer nodes each run with a fresh chat history, so
without this snapshot day N+1 has no visibility into commitments day N made
(hotel checkout time, return-flight number, car pickup location, running cost,
etc.). Injecting a tight `trip_state` block into the next node's prompt
restores that continuity without needing a shared message history.

Output is plain dict → JSON so it renders cleanly in a prompt and keeps the
prompt deterministic (no free-form LLM summary that could hallucinate).
"""
from typing import Any, Dict, List, Optional


def _coords_pair(c: Any) -> Optional[Dict[str, float]]:
    if not isinstance(c, dict):
        return None
    lat = c.get("latitude")
    lng = c.get("longitude")
    if lat is None or lng is None:
        return None
    try:
        return {"latitude": round(float(lat), 5), "longitude": round(float(lng), 5)}
    except (TypeError, ValueError):
        return None


def _first_cost(details: Dict[str, Any]) -> Optional[float]:
    for key in ("cost", "estimated_cost", "price", "total_cost", "trip_cost"):
        v = details.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def build_trip_state(prior_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarise prior_events into actionable structured state.

    Shape (all keys present, lists possibly empty):
      {
        "hotels": [ {hotel_name, address, coordinates, checkin, checkout, nights_days: [..]} ],
        "flights": [ {kind: "takeoff"|"land", flight_number, airline,
                      departure_airport, arrival_airport, departure_time, arrival_time,
                      day_number, event_number} ],
        "car_rentals": [ {kind: "pickup"|"dropoff", name, address, time,
                          day_number, event_number, vehicle} ],
        "activities_dining": [ {day, event_number, type, name, time} ],  # compact
        "commutes_count_per_day": {day: n},
        "cost_summary": { "total_committed": float, "per_event": [{day, event_number, type, name, cost}] },
        "current_position": {name, address, coordinates, last_day, last_event_number,
                             last_event_type, last_end_time}
      }
    """
    hotels: Dict[str, Dict[str, Any]] = {}   # keyed by hotel_name
    flights: List[Dict[str, Any]] = []
    car_rentals: List[Dict[str, Any]] = []
    activities_dining: List[Dict[str, Any]] = []
    commutes_count: Dict[int, int] = {}
    per_event_cost: List[Dict[str, Any]] = []
    total_cost: float = 0.0

    # Track "current position" by walking chronologically; take the last event
    # that has a meaningful end location.
    current_position: Optional[Dict[str, Any]] = None

    for e in prior_events:
        et = e.get("event_type") or ""
        day = e.get("day_number")
        evnum = e.get("event_number")
        name = e.get("event_name") or ""

        def _details(field: str) -> Dict[str, Any]:
            v = e.get(field)
            return v if isinstance(v, dict) else {}

        if et == "HOTEL_CHECKIN":
            d = _details("hotel_checkin_details")
            hname = d.get("hotel_name") or ""
            hotels.setdefault(hname, {
                "hotel_name": hname,
                "address": d.get("address"),
                "coordinates": _coords_pair(d.get("hotel_coordinates")),
                "checkin": {
                    "day_number": day,
                    "event_number": evnum,
                    "start_time": d.get("start_time"),
                    "end_time": d.get("end_time"),
                },
                "checkout": None,
                "booking_url": d.get("booking_url"),
            })
            current_position = {
                "name": hname,
                "address": d.get("address"),
                "coordinates": _coords_pair(d.get("hotel_coordinates")),
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time"),
            }
        elif et == "HOTEL_CHECKOUT":
            d = _details("hotel_checkout_details")
            hname = d.get("hotel_name") or ""
            entry = hotels.setdefault(hname, {
                "hotel_name": hname,
                "address": d.get("address"),
                "coordinates": _coords_pair(d.get("hotel_coordinates")),
                "checkin": None,
                "checkout": None,
                "booking_url": d.get("booking_url"),
            })
            entry["checkout"] = {
                "day_number": day,
                "event_number": evnum,
                "start_time": d.get("start_time"),
                "end_time": d.get("end_time"),
            }
            current_position = {
                "name": hname,
                "address": d.get("address"),
                "coordinates": _coords_pair(d.get("hotel_coordinates")),
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time"),
            }
        elif et in ("FLIGHT_TAKEOFF", "FLIGHT_LAND"):
            field = "flight_takeoff_details" if et == "FLIGHT_TAKEOFF" else "flight_land_details"
            d = _details(field)
            flights.append({
                "kind": "takeoff" if et == "FLIGHT_TAKEOFF" else "land",
                "day_number": day,
                "event_number": evnum,
                "flight_number": d.get("flight_number"),
                "airline": d.get("airline"),
                "departure_airport": d.get("departure_airport"),
                "arrival_airport": d.get("arrival_airport"),
                "departure_time": d.get("departure_time") or d.get("start_time"),
                "arrival_time": d.get("arrival_time") or d.get("end_time"),
                "booking_url": d.get("booking_url"),
            })
            coords = _coords_pair(d.get("arrival_coordinates"))
            current_position = {
                "name": d.get("arrival_airport") or "",
                "address": None,
                "coordinates": coords,
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time") or d.get("arrival_time"),
            }
        elif et in ("CAR_PICKUP", "CAR_DROPOFF"):
            if et == "CAR_PICKUP":
                d = _details("car_pickup_details")
                loc_name = d.get("pickup_location_name")
                loc_addr = d.get("pickup_location_address")
                coords = _coords_pair(d.get("pickup_location_coordinates"))
            else:
                d = _details("car_dropoff_details")
                loc_name = d.get("dropoff_location_name")
                loc_addr = d.get("dropoff_location_address")
                coords = _coords_pair(d.get("dropoff_location_coordinates"))
            veh = d.get("vehicle_details") or {}
            car_rentals.append({
                "kind": "pickup" if et == "CAR_PICKUP" else "dropoff",
                "day_number": day,
                "event_number": evnum,
                "name": loc_name,
                "address": loc_addr,
                "coordinates": coords,
                "time": d.get("start_time") or d.get("end_time"),
                "vehicle": {
                    "make": veh.get("make"),
                    "model": veh.get("model"),
                    "type": veh.get("type"),
                } if isinstance(veh, dict) else None,
                "booking_url": d.get("booking_url"),
            })
            current_position = {
                "name": loc_name or "",
                "address": loc_addr,
                "coordinates": coords,
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time"),
            }
        elif et == "COMMUTE":
            d = _details("commute_details")
            commutes_count[day] = commutes_count.get(day, 0) + 1
            current_position = {
                "name": d.get("destinationName") or "",
                "address": None,
                "coordinates": _coords_pair(d.get("destination_coordinates")),
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time"),
            }
        elif et in ("DINING", "ACTIVITY"):
            d = _details("place_details")
            activities_dining.append({
                "day_number": day,
                "event_number": evnum,
                "type": et,
                "name": d.get("place_name") or name,
                "start_time": d.get("start_time"),
                "end_time": d.get("end_time"),
            })
            current_position = {
                "name": d.get("place_name") or name,
                "address": d.get("address"),
                "coordinates": _coords_pair(d.get("coordinates")),
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time"),
            }
        elif et == "OTHER":
            d = _details("other_details")
            current_position = {
                "name": d.get("place_name") or name,
                "address": d.get("address"),
                "coordinates": _coords_pair(d.get("coordinates")),
                "last_day": day,
                "last_event_number": evnum,
                "last_event_type": et,
                "last_end_time": d.get("end_time"),
            }

        # Accumulate committed cost (same heuristic the finalizer uses).
        for v in e.values():
            if isinstance(v, dict):
                c = _first_cost(v)
                if c is not None:
                    per_event_cost.append({
                        "day_number": day,
                        "event_number": evnum,
                        "type": et,
                        "name": name,
                        "cost": c,
                    })
                    total_cost += c
                    break

    return {
        "hotels": list(hotels.values()),
        "flights": flights,
        "car_rentals": car_rentals,
        "activities_dining": activities_dining,
        "commutes_count_per_day": commutes_count,
        "cost_summary": {
            "total_committed": round(total_cost, 2),
            "per_event": per_event_cost,
        },
        "current_position": current_position or {},
    }
