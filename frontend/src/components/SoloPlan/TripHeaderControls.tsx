import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  BedDouble,
  Car,
  ExternalLink,
  Loader2,
  PlaneTakeoff,
  Trash2,
  X,
} from 'lucide-react';
import { isValidUrl } from './constants';
import type { ItineraryState } from './types';

type BookingLink = {
  key: string;
  type: string;
  label: string;
  Icon: typeof ExternalLink;
  url: string;
  detail: string;
};

function cleanText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function domainLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

function bookingLabel(type: 'flight' | 'hotel' | 'rental car', url: string): string {
  const domain = domainLabel(url);
  return domain ? `Book ${type} on ${domain}` : `Book ${type}`;
}

function addBookingLink(target: BookingLink[], item: Omit<BookingLink, 'key'>) {
  if (!isValidUrl(item.url)) return;
  const url = item.url.trim();
  if (target.some((existing) => existing.url === url)) return;
  target.push({ ...item, key: `${item.type}-${target.length}-${url}`, url });
}

function collectBookingLinks(itineraryState: ItineraryState): BookingLink[] {
  const links: BookingLink[] = [];

  for (const day of itineraryState.days || []) {
    for (const event of day.events || []) {
      const dayPrefix = typeof day.dayNumber === 'number' ? `Day ${day.dayNumber}` : '';
      const flight = event.flight_takeoff_details;
      if (flight?.booking_url) {
        const url = cleanText(flight.booking_url);
        const airline = cleanText(flight.airline) || 'Flight';
        const flightNumber = cleanText(flight.flight_number);
        const route = [cleanText(flight.departure_airport_code), cleanText(flight.arrival_airport_code)]
          .filter(Boolean)
          .join(' to ');
        addBookingLink(links, {
          type: 'Flight',
          label: flightNumber ? `${airline} ${flightNumber}` : airline === 'Flight' ? bookingLabel('flight', url) : airline,
          detail: [dayPrefix, route].filter(Boolean).join(' - '),
          Icon: PlaneTakeoff,
          url,
        });
      }

      const hotel = event.hotel_checkin_details;
      if (hotel?.booking_url) {
        const url = cleanText(hotel.booking_url);
        addBookingLink(links, {
          type: 'Hotel',
          label: cleanText(hotel.hotel_name) || bookingLabel('hotel', url),
          detail: [dayPrefix, cleanText(hotel.address)].filter(Boolean).join(' - '),
          Icon: BedDouble,
          url,
        });
      }

      const rental = event.car_pickup_details;
      if (rental?.booking_url) {
        const url = cleanText(rental.booking_url);
        const vehicleName = cleanText(rental.vehicle?.vehicle_name);
        const company = cleanText(rental.rental_company_name);
        addBookingLink(links, {
          type: 'Rental Car',
          label: vehicleName || company || bookingLabel('rental car', url),
          detail: [dayPrefix, company, cleanText(rental.pickup_location_name)].filter(Boolean).join(' - '),
          Icon: Car,
          url,
        });
      }
    }
  }

  return links;
}

function HeaderIconButton({
  onClick,
  title,
  children,
  tone = 'cyan',
  disabled = false,
}: {
  onClick: () => void;
  title: string;
  children: ReactNode;
  tone?: 'cyan' | 'red' | 'white';
  disabled?: boolean;
}) {
  const tones = {
    cyan: 'border-white/10 bg-black/60 text-cyan hover:border-cyan/40 hover:bg-cyan/10',
    red: 'border-white/10 bg-black/60 text-red-300 hover:border-red-300/40 hover:bg-red-400/10',
    white: 'border-white/10 bg-black/60 text-white/65 hover:border-white/25 hover:bg-white/10 hover:text-white',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-10 w-10 shrink-0 rounded-full border backdrop-blur-md flex items-center justify-center transition-all disabled:cursor-not-allowed disabled:opacity-50 ${tones[tone]}`}
      title={title}
      aria-label={title}
    >
      {children}
    </button>
  );
}

export function TripNavigationControls({
  canDelete,
  deleting,
  deleteDisabled,
  onBack,
  onDelete,
}: {
  canDelete: boolean;
  deleting: boolean;
  deleteDisabled?: boolean;
  onBack: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="relative flex items-center gap-2">
      <HeaderIconButton onClick={onBack} title="Back to home" tone="white">
        <ArrowLeft className="h-4 w-4" />
      </HeaderIconButton>
      {canDelete && (
        <HeaderIconButton onClick={onDelete} title="Delete trip" tone="red" disabled={deleting || deleteDisabled}>
          {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
        </HeaderIconButton>
      )}
    </div>
  );
}

export function DeleteTripModal({
  tripTitle,
  deleting,
  error,
  onCancel,
  onConfirm,
}: {
  tripTitle: string;
  deleting: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-carbon p-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-red-300/30 bg-red-400/10 text-red-300">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h4 className="text-sm font-bold text-white">Delete Trip?</h4>
            <p className="mt-2 text-xs leading-relaxed text-white/50">
              This permanently deletes {tripTitle || 'this trip'} and its generated itinerary.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="rounded-lg p-1.5 text-white/35 transition-colors hover:bg-white/5 hover:text-white"
            title="Close"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {error && <p className="mt-4 text-xs text-red-300">{error}</p>}
        <div className="mt-5 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="rounded-xl border border-white/10 px-3 py-2 text-xs font-bold uppercase tracking-wide text-white/60 transition-colors hover:bg-white/[0.05] hover:text-white disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={deleting}
            className="flex items-center justify-center gap-2 rounded-xl bg-red-400 px-3 py-2 text-xs font-bold uppercase tracking-wide text-midnight transition-colors hover:bg-red-300 disabled:opacity-50"
          >
            {deleting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

export function OpenBookingsMenu({ itineraryState }: { itineraryState: ItineraryState }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const bookingLinks = useMemo(() => collectBookingLinks(itineraryState), [itineraryState]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const isInsideMenu = (target: EventTarget | null) =>
      target instanceof Node && rootRef.current?.contains(target);
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) close();
    };
    const onOutsideScroll = (event: Event) => {
      if (!isInsideMenu(event.target)) close();
    };
    document.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('scroll', onOutsideScroll, true);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('scroll', onOutsideScroll, true);
    };
  }, [open]);

  if (bookingLinks.length === 0) return null;

  return (
    <div ref={rootRef} className="flex items-center">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        title="Open booking links"
        aria-label="Open booking links"
        className={`h-10 w-10 shrink-0 rounded-full border backdrop-blur-md flex items-center justify-center transition-all ${open ? 'border-cyan/40 bg-cyan text-midnight shadow-[0_0_18px_rgba(102,252,241,0.25)]' : 'border-white/10 bg-black/60 text-cyan hover:border-cyan/40 hover:bg-cyan/10'}`}
      >
        <ExternalLink className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-[80] w-[min(92vw,380px)] rounded-2xl border border-white/10 bg-carbon/95 shadow-2xl backdrop-blur-xl flex flex-col max-h-[min(80vh,560px)]">
          <div className="border-b border-white/5 px-4 py-3 shrink-0">
            <h3 className="text-sm font-bold text-white">Bookings</h3>
            <p className="mt-0.5 text-[11px] text-white/40">Flights, hotels, and rental cars</p>
          </div>
          <div className="flex flex-1 min-h-0 flex-col gap-2 overflow-y-auto p-3 chat-scrollbar">
            {bookingLinks.map(({ key, type, label, detail, Icon, url }) => (
              <a
                key={key}
                href={url}
                target="_blank"
                rel="noreferrer"
                title={url}
                onClick={() => setOpen(false)}
                className="flex min-h-16 items-center gap-3 rounded-xl border border-white/10 bg-black/25 px-3 py-2.5 text-left text-cyan transition-colors hover:border-cyan/35 hover:bg-cyan/10"
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block text-[10px] font-bold uppercase tracking-[0.14em] text-white/35">{type}</span>
                  <span className="mt-0.5 block truncate text-sm font-bold text-white">{label}</span>
                  {detail && <span className="mt-0.5 block truncate text-[11px] text-white/40">{detail}</span>}
                </span>
                <span className="shrink-0 rounded-full border border-cyan/25 bg-cyan/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-cyan">
                  Open
                </span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
