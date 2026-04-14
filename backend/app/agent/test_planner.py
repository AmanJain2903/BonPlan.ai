import asyncio
import json
from app.agent.planner import generate_trip_itinerary

test_trip_payload = {
    "owner_id": "98c1837d-b37d-42aa-b3d0-5d185fe9d843",
    "trip_id": "1b3df3fa-b334-4754-8213-c2b84f07372c",
    "hasMultipleDestinations": False,
    "planning_type": "SOLO",
    "origin": {
        "lat": 37.3541079,
        "lng": -121.9552356,
        "city": "Santa Clara",
        "state": "CA",
        "country": "United States"
    },
    "routing_style": "SINGLE_HUB",
    "destinations": [
        {
            "lat": 37.7749295,
            "lng": -122.4194155,
            "city": "San Francisco",
            "state": "CA",
            "country": "United States"
        }
    ],
    "start_date": {
        "day": 29,
        "year": 2026,
        "month": 4,
        "timezoneId": "America/Los_Angeles",
        "utcTimestamp": 1777446000,
        "utcTimeString": "2026-04-29T07:00:00Z",
        "localTimeString": "2026-04-29T00:00:00"
    },
    "end_date": {
        "day": 30,
        "year": 2026,
        "month": 4,
        "timezoneId": "America/Los_Angeles",
        "utcTimestamp": 1777532400,
        "utcTimeString": "2026-04-30T07:00:00Z",
        "localTimeString": "2026-04-30T23:59:00"
    },
    "pace": "Active Explorer",
    "budget": "Moderate",
    "adults": 1,
    "children": 0,
    "preferences": {
        "dining_style": "mid_range_sit_down",
        "schedule_rhythm": "standard",
        "other_preferences": {
            "pet_friendly": False,
            "child_friendly": False,
            "alcohol_allowed": True,
            "smoking_allowed": True,
            "additional_notes": "I prefer low budget activities, dining and accommodation.",
            "toddler_friendly": False,
            "ev_charging_available": False
        },
        "activity_interests": ["nature_and_hiking", "coffee_shop_hopping", "photography_spots", "nightlife"],
        "travel_preferences": {"travel_to_destination": "rental_car", "travel_around_destination": "walking"},
        "accommodation_style": "any",
        "dietary_restrictions": ["Vegetarian"],
        "accessibility_preferences": "standard"
    }
}

async def run_test():
    print("Testing the BonPlan Planner Agent...")
    print("-------------------------------------")
    try:
        # the function returns an async generator
        async for chunk in generate_trip_itinerary(test_trip_payload):
            chunk_type = chunk.get("type", "unknown")
            
            if chunk_type == "thinking":
                print(f"{chunk.get('content')}", end="", flush=True)
            elif chunk_type == "summary":
                print(f"{chunk.get('content')}")
            elif chunk_type == "tool_call":
                args_str = json.dumps(chunk.get('args', {}))
                print(f"\n[TOOL CALL] {chunk.get('tool_name')} | Args: {args_str}")
            elif chunk_type == "tool_response":
                print(f"[TOOL RESPONSE] {chunk.get('tool_name')} returned: {json.dumps(chunk.get('response'), indent=2)[:500]} ... [truncated]")
            elif chunk_type == "event":
                print(f"\n=============================================")
                print(f"[NEW ITINERARY EVENT EMITTED]")
                print(json.dumps(chunk.get("data", {}), indent=2))
                print(f"=============================================\n")
            elif chunk_type == "system":
                print(f"\n[SYSTEM] {chunk.get('content')}")
            elif chunk_type == "error":
                print(f"\n[ERROR] {chunk.get('content')}")
            else:
                print(f"\n[UNKNOWN CHUNK] {chunk}")
                
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Failed to run test: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
