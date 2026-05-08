import type { ReactNode } from 'react';
import FlightTakeoffCard from './FlightTakeoffCard';
import FlightLandCard from './FlightLandCard';
import HotelCheckinCard from './HotelCheckinCard';
import HotelCheckoutCard from './HotelCheckoutCard';
import CarPickupCard from './CarPickupCard';
import CarDropoffCard from './CarDropoffCard';
import DiningCard from './DiningCard';
import ActivityCard from './ActivityCard';
import OtherCard from './OtherCard';
import CommuteConnector from './CommuteConnector';

export {
  FlightTakeoffCard,
  FlightLandCard,
  HotelCheckinCard,
  HotelCheckoutCard,
  CarPickupCard,
  CarDropoffCard,
  DiningCard,
  ActivityCard,
  OtherCard,
  CommuteConnector,
};

/**
 * Selector: returns the matching subcard (or commute connector) for a given event.
 * Returns null for START/END or unknown types.
 *
 * Each subcard receives `contentKey` derived from `_updatedAt` so that when an
 * event is edited by the AI, the subcard's content crossfades smoothly.
 */
export function renderSubCardForEvent(
  event: any,
  { onViewOnMap, onToggleLock }: { onViewOnMap: (event: any) => void; onToggleLock?: (event: any) => void },
): ReactNode {
  if (!event) return null;
  const handler = () => onViewOnMap(event);
  const lockHandler = onToggleLock ? () => onToggleLock(event) : undefined;
  const contentKey = event._updatedAt || 'init';
  switch (event.event_type) {
    case 'FLIGHT_TAKEOFF':
      return <FlightTakeoffCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'FLIGHT_LAND':
      return <FlightLandCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'HOTEL_CHECKIN':
      return <HotelCheckinCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'HOTEL_CHECKOUT':
      return <HotelCheckoutCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'CAR_PICKUP':
      return <CarPickupCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'CAR_DROPOFF':
      return <CarDropoffCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'DINING':
      return <DiningCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'ACTIVITY':
      return <ActivityCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'OTHER':
      return <OtherCard event={event} onViewOnMap={handler} onToggleLock={lockHandler} contentKey={contentKey} />;
    case 'COMMUTE':
      return <CommuteConnector event={event} contentKey={contentKey} />;
    default:
      return null;
  }
}
