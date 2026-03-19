import { createContext, useContext, useCallback, useMemo, useState, type ReactNode } from 'react';
export type PlanningStyle = 'solo' | 'squad';
export type RoutingStyle = 'single-hub' | 'multi-hop';

export type Place = {
  city: string | null;
  state: string | null;
  country: string | null;
  lat: number | null;
  lng: number | null;
};

export type TripDate = {
  month: number | null;
  day: number | null;
  year: number | null;
  timezoneId: string | null;
};

export type TripData = {
  origin: Place | null;
  destinations: Place[] | null;
  startDate: TripDate | null;
  endDate: TripDate | null;
  pace: string | null;
  budget: string | null;
  conversationalContext: string | null;
  adults: number | null;
  children: number | null;
}

export type TripDraft = {
  planningStyle: PlanningStyle | null;
  routingStyle: RoutingStyle | null;
  tripData: TripData | null;
};

type TripContextValue = {
  trip: TripDraft;
  setTrip: (patch: Partial<TripDraft>) => void;
  updateTripData: (patch: any) => void;
  resetTrip: () => void;
};

const TripContext = createContext<TripContextValue | null>(null);

const EMPTY_TRIP: TripDraft = { planningStyle: null, routingStyle: null, tripData: null };

const TRIP_KEY = 'bonplan.tripDraft';
const PLAN_STEP_KEY = 'bonplan.planStepIndex';

function loadTrip(): TripDraft {
  const raw = sessionStorage.getItem(TRIP_KEY);
  if (!raw) return EMPTY_TRIP;
  try {
    const parsed = JSON.parse(raw) as Partial<TripDraft> | null;
    return {
      planningStyle: parsed?.planningStyle === 'solo' || parsed?.planningStyle === 'squad' ? parsed.planningStyle : null,
      routingStyle: parsed?.routingStyle === 'single-hub' || parsed?.routingStyle === 'multi-hop' ? parsed.routingStyle : null,
      tripData: typeof parsed?.tripData === 'object' ? parsed.tripData : null,
    };
  } catch {
    return EMPTY_TRIP;
  }
}

export function TripProvider({ children }: { children: ReactNode }) {
  const [trip, setTripState] = useState<TripDraft>(() => loadTrip());

  const setTrip = useCallback((patch: Partial<TripDraft>) => {
    setTripState((prev) => {
      const next = { ...prev, ...patch };
      sessionStorage.setItem(TRIP_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const updateTripData = useCallback((patch: Partial<TripData>) => {
    setTripState((prev) => {

      const nextTripData = prev.tripData
        ? { ...prev.tripData, ...patch }
        : { ...patch };

      const next = { ...prev, tripData: nextTripData as TripData };

      sessionStorage.setItem(TRIP_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const resetTrip = useCallback(() => {
    setTripState(EMPTY_TRIP);
    sessionStorage.removeItem(TRIP_KEY);
    sessionStorage.removeItem(PLAN_STEP_KEY);
  }, []);

  const value = useMemo(() => ({ trip, setTrip, updateTripData, resetTrip }), [trip, setTrip, updateTripData, resetTrip]);

  return <TripContext.Provider value={value}>{children}</TripContext.Provider>;
}

export function useTrip() {
  const ctx = useContext(TripContext);
  if (!ctx) throw new Error('useTrip must be used within a TripProvider');
  return ctx;
}

