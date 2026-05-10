import type { TripItinerary } from '../../apis/plan';
import type { ItineraryState, ItineraryDay } from './types';
import {
  Plane,
  PlaneLanding,
  PlaneTakeoff,
  BedDouble,
  BedSingle,
  Car,
  UtensilsCrossed,
  Compass,
  Sparkles,
  Navigation,
} from 'lucide-react';

// ─── Shared Animation Presets ─────────────────────────────────
export const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const;

export const SPRING_PILL = { type: 'spring' as const, stiffness: 400, damping: 30 };

export const BOUNCE_DOT_TRANSITION = (i: number) => ({
  duration: 1.2,
  repeat: Infinity,
  delay: i * 0.2,
  ease: 'easeInOut' as const,
});

export const SHIMMER_WIDTHS = [0.5, 0.7, 0.9, 0.6, 0.8];

// ─── Shared Utilities ─────────────────────────────────────────
export const safelyParseJSON = (jsonString: any) => {
  if (typeof jsonString === 'object') return jsonString;
  try {
    return JSON.parse(jsonString);
  } catch {
    return null;
  }
};

export const formatDate = (dateObj: any) => {
  if (!dateObj) return '';
  const parsed = safelyParseJSON(dateObj);
  if (parsed?.year && parsed?.month && parsed?.day) {
    const d = new Date(parsed.year, parsed.month - 1, parsed.day);
    if (!isNaN(d.getTime()))
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  return '';
};

export const getDateDifference = (start?: any, end?: any): number => {
  if (!start || !end) return 0;

  // 1. Convert to Date objects (handles ISO strings and objects)
  const s = new Date(start);
  const e = new Date(end);

  // 2. Normalize both to Midnight (00:00:00) in the same timezone
  // This ensures we are comparing "Calendar Days" regardless of the hour
  const startDate = new Date(s.getFullYear(), s.getMonth(), s.getDate());
  const endDate = new Date(e.getFullYear(), e.getMonth(), e.getDate());

  // 3. Calculate difference in days
  const msPerDay = 1000 * 60 * 60 * 24;
  const diff = endDate.getTime() - startDate.getTime();
  
  return Math.round(diff / msPerDay);
};

export const formatDateForDayCard = (date: string) => {
  const year = date.split('-')[0];
  const month = date.split('-')[1];
  const day = date.split('-')[2];
  const monthMap = {
    '01': 'January',
    '02': 'February',
    '03': 'March',
    '04': 'April',
    '05': 'May',
    '06': 'June',
    '07': 'July',
    '08': 'August',
    '09': 'September',
    '10': 'October',
    '11': 'November',
    '12': 'December'
  }
  return `${day}-${monthMap[month as keyof typeof monthMap]}-${year}`;
}

// ─── Shared Formatting Helpers ────────────────────────────────

/** Convert meters → formatted English miles string, e.g. "25 Miles", "0.4 Miles", "1 Mile". */
export const formatMiles = (meters: number): string => {
  if (!Number.isFinite(meters) || meters <= 0) return '0 Miles';
  const miles = meters * 0.000621371;
  if (miles < 10) {
    const rounded = Math.round(miles * 10) / 10;
    if (rounded === 1) return '1 Mile';
    return `${rounded} Miles`;
  }
  const rounded = Math.round(miles);
  if (rounded === 1) return '1 Mile';
  return `${rounded} Miles`;
};

/** Natural English duration for a number of seconds. e.g. "45 seconds", "31 minutes", "2 hours 31 minutes", "2 hours". */
export const formatDurationEnglish = (seconds?: number, start?: any, end?: any): string | null => {
  if (start && end) {
    const startObj = safelyParseJSON(start);
    const endObj = safelyParseJSON(end);
    if (startObj && endObj) {
      if (startObj.year && startObj.month && startObj.day && startObj.hour && startObj.minute && endObj.year && endObj.month && endObj.day && endObj.hour && endObj.minute) {
        const startDate = new Date(startObj.year, startObj.month - 1, startObj.day, startObj.hour, startObj.minute);
        const endDate = new Date(endObj.year, endObj.month - 1, endObj.day, endObj.hour, endObj.minute);
        const diff = Math.round((endDate.getTime() - startDate.getTime()) / 1000);
        seconds = diff;
      }
    }
  }
  if (!seconds || seconds === 0) return null;
  if (!Number.isFinite(seconds) || seconds <= 0) return '0 minutes';
  const total = Math.round(seconds);
  if (total < 60) {
    return total === 1 ? '1 second' : `${total} seconds`;
  }
  if (total < 3600) {
    const m = Math.round(total / 60);
    return m === 1 ? '1 minute' : `${m} minutes`;
  }
  const h = Math.floor(total / 3600);
  const m = Math.round((total - h * 3600) / 60);
  const hStr = h === 1 ? '1 hour' : `${h} hours`;
  if (m === 0) return hStr;
  const mStr = m === 1 ? '1 minute' : `${m} minutes`;
  return `${hStr} ${mStr}`;
};

/** True when `u` is a non-empty string that parses as an http(s) URL. */
export const isValidUrl = (u?: string | null): boolean => {
  if (!u || typeof u !== 'string') return false;
  const s = u.trim();
  if (!s) return false;
  try {
    const parsed = new URL(s);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
};

/** Formats an ISO "YYYY-MM-DDTHH:MM:SS" timestamp as a short clock time "h:mm AM/PM". */
export const formatClockTime = (iso?: string | null): string => {
  if (!iso) return '';
  const time = iso.includes('T') ? iso.split('T')[1] : iso;
  if (!time) return '';
  const parts = time.split(':');
  if (parts.length < 2) return '';
  let h = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return '';
  const suffix = h >= 12 ? 'PM' : 'AM';
  h = h % 12;
  if (h === 0) h = 12;
  return `${h}:${m.toString().padStart(2, '0')} ${suffix}`;
};

/** Sum of distanceMeters across all COMMUTE events on a day. */
export const metersFromCommutes = (events: any[]): number =>
  (events || [])
    .filter((e) => e?.event_type === 'COMMUTE' && e?.commute_details)
    .reduce((m, e) => m + (e.commute_details.distanceMeters || 0), 0);

// ─── Event Type Metadata ──────────────────────────────────────

export const EVENT_ICON = {
  FLIGHT_TAKEOFF: PlaneTakeoff,
  FLIGHT_LAND: PlaneLanding,
  HOTEL_CHECKIN: BedDouble,
  HOTEL_CHECKOUT: BedSingle,
  CAR_PICKUP: Car,
  CAR_DROPOFF: Car,
  DINING: UtensilsCrossed,
  ACTIVITY: Compass,
  COMMUTE: Navigation,
  OTHER: Sparkles,
  DEFAULT: Plane,
} as const;

export const EVENT_LABEL: Record<string, string> = {
  FLIGHT_TAKEOFF: 'Takeoff',
  FLIGHT_LAND: 'Landing',
  HOTEL_CHECKIN: 'Check-in',
  HOTEL_CHECKOUT: 'Check-out',
  CAR_PICKUP: 'Pickup',
  CAR_DROPOFF: 'Dropoff',
  DINING: 'Dining',
  ACTIVITY: 'Activity',
  COMMUTE: 'Commute',
  OTHER: 'Event',
};

/** Tailwind color tokens associated with each event type (for icon/accent coloring). */
export const EVENT_ACCENT: Record<string, { text: string; bg: string; border: string; marker: string }> = {
  FLIGHT_TAKEOFF: { text: 'text-sky-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#7dd3fc' },
  FLIGHT_LAND: { text: 'text-indigo-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#a5b4fc' },
  HOTEL_CHECKIN: { text: 'text-emerald-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#6ee7b7' },
  HOTEL_CHECKOUT: { text: 'text-emerald-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#a7f3d0' },
  CAR_PICKUP: { text: 'text-amber-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#fcd34d' },
  CAR_DROPOFF: { text: 'text-amber-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#fde68a' },
  DINING: { text: 'text-rose-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#fda4af' },
  ACTIVITY: { text: 'text-cyan-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#67e8f9' },
  COMMUTE: { text: 'text-cyan-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#a5f3fc' },
  OTHER: { text: 'text-fuchsia-300', bg: 'bg-cyan-400/10', border: 'border-cyan-400/30', marker: '#f0abfc' },
};


export const eventIdentityKey = (event: any): string => {
  if (event?.event_id) return `id:${event.event_id}`;
  return `legacy:${event?.day_number}-${event?.event_number}`;
};

const eventSortValue = (event: any): number => {
  const sort = Number(event?.event_sort_key);
  if (Number.isFinite(sort)) return sort;
  const display = Number(event?.display_event_number);
  if (Number.isFinite(display)) return display * 1000;
  const legacy = Number(event?.event_number);
  return Number.isFinite(legacy) ? legacy * 1000 : 0;
};

/** Stable per-event key used for navigation highlights (view-on-map, etc). */
export const eventKey = (event: any): string =>
  event?.event_id ? `event-${event.event_id}` : `${event?.event_type}-d${event?.day_number}-e${event?.event_number}`;

function normalizeCoordinates(input: any): { latitude: number; longitude: number } | null {
  if (!input) return null;
  const latitude = typeof input.latitude === 'number' ? input.latitude : input.lat;
  const longitude = typeof input.longitude === 'number' ? input.longitude : input.lng;
  if (typeof latitude !== 'number' || typeof longitude !== 'number') return null;
  return { latitude, longitude };
}

/** Pick a coordinates object from an event, if the event type carries coordinates. */
export const coordinatesForEvent = (event: any): { latitude: number; longitude: number } | null => {
  if (!event) return null;
  switch (event.event_type) {
    case 'FLIGHT_TAKEOFF':
      return normalizeCoordinates(event.flight_takeoff_details?.departure_coordinates);
    case 'FLIGHT_LAND':
      return normalizeCoordinates(event.flight_land_details?.arrival_coordinates);
    case 'HOTEL_CHECKIN':
    case 'HOTEL_CHECKOUT':
      return normalizeCoordinates(
        (event.hotel_checkin_details || event.hotel_checkout_details)?.hotel_coordinates,
      );
    case 'CAR_PICKUP':
      return normalizeCoordinates(event.car_pickup_details?.pickup_location_coordinates);
    case 'CAR_DROPOFF':
      return normalizeCoordinates(event.car_dropoff_details?.dropoff_location_coordinates);
    case 'DINING':
    case 'ACTIVITY':
      return normalizeCoordinates(event.place_details?.coordinates);
    case 'OTHER':
      return normalizeCoordinates(event.other_details?.coordinates);
    default:
      return null;
  }
};

// ─── Replay Events from DB ───────────────────────────────────

function getEventCost(data: any): number {
  switch (data.event_type) {
    case 'FLIGHT_TAKEOFF':
      return data.flight_takeoff_details?.cost || 0;
    case 'HOTEL_CHECKIN':
      return data.hotel_checkin_details?.cost || 0;
    case 'ACTIVITY':
    case 'DINING':
      return data.place_details?.cost || 0;
    case 'CAR_PICKUP':
      return data.car_pickup_details?.cost || 0;
    case 'COMMUTE':
      return data.commute_details?.transit_fare || 0;
    case 'OTHER':
      return data.other_details?.cost || 0;
    default:
      return 0;
  }
}

function isCountableEvent(eventType: string): boolean {
  return ['HOTEL_CHECKIN', 'ACTIVITY', 'DINING', 'OTHER'].includes(eventType);
}

export function replayEvents(itinerary: TripItinerary): ItineraryState {
  const events = itinerary.events || [];
  const startEvent = events.find((event: any) => event?.event_type === 'START');
  const totalDays = itinerary.days || startEvent?.start_details?.number_of_days || null;
  const isFullyGenerated = (itinerary.status || '').toUpperCase() === 'GENERATED';

  if (events.length === 0 && totalDays == null) {
    return {
      tripTitle: itinerary.title || undefined,
      tripCostEstimate: itinerary.cost ?? undefined,
      journey: itinerary.destinations?.length ? itinerary.destinations : undefined,
      days: [],
      hasStarted: false,
      tripTips: itinerary.tips?.length ? itinerary.tips : undefined,
      snapshotCursor: itinerary.snapshot_cursor,
      eventsHash: itinerary.events_hash,
    };
  }

  const dayCount = totalDays || 0;
  const dayMap = new Map<number, ItineraryDay>();

  for (let i = 1; i <= dayCount; i++) {
    dayMap.set(i, {
      dayNumber: i,
      title: '',
      date: '',
      events: [],
      eventsCount: 0,
      cost: 0,
      isLoading: !isFullyGenerated,
      hasError: false,
    });
  }

  for (const event of events) {
    if (event.event_type === 'START' || event.event_type === 'END') continue;

    const dayNum = event.day_number;
    if (typeof dayNum !== 'number' || dayNum <= 0) continue;

    let day = dayMap.get(dayNum);
    if (!day) {
      day = {
        dayNumber: dayNum,
        title: '',
        date: '',
        events: [],
        eventsCount: 0,
        cost: 0,
        isLoading: !isFullyGenerated,
        hasError: false,
      };
      dayMap.set(dayNum, day);
    }

    if (event.day_title && typeof event.day_title === 'string' && !['end', 'start'].includes(event.day_title.toLowerCase().trim())) {
      day.title = event.day_title;
    }
    if (!day.date && event.date && typeof event.date === 'string' && !['end', 'start'].includes(event.date.toLowerCase().trim())) {
      day.date = event.date;
    }

    // Editing uses stable event_id + event_sort_key so insertions/moves do not
    // require legacy event_number renumbering. Older generation events fall
    // back to (day_number,event_number).
    const existingIdx = day.events.findIndex(
      (e: any) => eventIdentityKey(e) === eventIdentityKey(event),
    );
    if (existingIdx === -1) {
      day.events.push(event);
      day.cost += getEventCost(event);
      if (isCountableEvent(event.event_type)) {
        day.eventsCount += 1;
      }
    } else {
      const prev = day.events[existingIdx];
      day.cost = day.cost - getEventCost(prev) + getEventCost(event);
      const prevCountable = isCountableEvent(prev.event_type) ? 1 : 0;
      const newCountable = isCountableEvent(event.event_type) ? 1 : 0;
      day.eventsCount = day.eventsCount - prevCountable + newCountable;
      day.events[existingIdx] = event;
    }
  }

  const daysWithEvents = new Set<number>();
  for (const event of events) {
    if (event.event_type !== 'START' && event.event_type !== 'END' && typeof event.day_number === 'number') {
      daysWithEvents.add(event.day_number);
    }
  }

  let maxDayWithEvents = 0;
  for (const d of daysWithEvents) {
    if (d > maxDayWithEvents) maxDayWithEvents = d;
  }

  for (const [dayNum, day] of dayMap) {
    if (isFullyGenerated) {
      day.isLoading = false;
    } else if (dayNum < maxDayWithEvents) {
      day.isLoading = false;
    } else if (daysWithEvents.has(dayNum)) {
      day.isLoading = true;
    }
  }

  const sortedDays = Array.from(dayMap.values()).sort((a, b) => a.dayNumber - b.dayNumber);
  for (const day of sortedDays) {
    day.events.sort((a: any, b: any) => eventSortValue(a) - eventSortValue(b));
  }

  return {
    tripTitle: itinerary.title || undefined,
    tripCostEstimate: itinerary.cost ?? undefined,
    journey: itinerary.destinations?.length ? itinerary.destinations : undefined,
    days: sortedDays,
    hasStarted: sortedDays.length > 0,
    tripTips: itinerary.tips?.length ? itinerary.tips : undefined,
    snapshotCursor: itinerary.snapshot_cursor,
    eventsHash: itinerary.events_hash,
  };
}
