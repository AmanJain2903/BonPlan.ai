import type { TripItinerary } from '../../apis/plan';
import type { ItineraryState, ItineraryDay } from './types';

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
  const totalDays = itinerary.days;
  const events = itinerary.events || [];
  const isFullyGenerated = (itinerary.status || '').toUpperCase() === 'GENERATED';

  if (events.length === 0 && totalDays == null) {
    return {
      tripTitle: itinerary.title || undefined,
      tripCostEstimate: itinerary.cost ?? undefined,
      journey: itinerary.destinations?.length ? itinerary.destinations : undefined,
      days: [],
      hasStarted: false,
      tripTips: itinerary.tips?.length ? itinerary.tips : undefined,
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

    day.title = event.day_title || day.title;
    day.date = event.date || day.date;
    day.events.push(event);
    day.cost += getEventCost(event);
    if (isCountableEvent(event.event_type)) {
      day.eventsCount += 1;
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

  return {
    tripTitle: itinerary.title || undefined,
    tripCostEstimate: itinerary.cost ?? undefined,
    journey: itinerary.destinations?.length ? itinerary.destinations : undefined,
    days: sortedDays,
    hasStarted: sortedDays.length > 0,
    tripTips: itinerary.tips?.length ? itinerary.tips : undefined,
  };
}