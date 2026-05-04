import { Car, DollarSign, MapPin, ExternalLink } from 'lucide-react';
import SubCardShell from './common/SubCardShell';
import TipsSection from './common/TipsSection';
import ViewOnMapButton from './common/ViewOnMapButton';
import { Dot } from '../Atoms';
import { EVENT_ACCENT, EVENT_ICON, EVENT_LABEL, formatClockTime, isValidUrl } from '../constants';

interface Props {
  event: any;
  onViewOnMap: () => void;
  contentKey?: string | number;
}

function LogoOrIcon({ url, name }: { url?: string; name: string }) {
  if (isValidUrl(url)) {
    return (
      <img
        src={url}
        alt={name}
        className="w-8 h-8 rounded-md bg-white object-contain p-1 shrink-0"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />
    );
  }
  return (
    <div className="w-8 h-8 flex items-center justify-center shrink-0 rounded-md bg-white">
      <Car className="w-4 h-4 text-black" />
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="px-2 py-1 rounded-full text-[11px] border bg-white/[0.04] border-cyan/30 text-white/75 flex items-center gap-1">
      {children}
    </span>
  );
}

export default function CarPickupCard({ event, onViewOnMap, contentKey }: Props) {
  const d = event?.car_pickup_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.CAR_PICKUP;
  const Icon = EVENT_ICON.CAR_PICKUP;
  const v = d.vehicle || {};

  return (
    <SubCardShell
      eventType="CAR_PICKUP"
      label={EVENT_LABEL.CAR_PICKUP}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      collapsedContent={
        <>
          <LogoOrIcon url={d.rental_company_logo_url} name={d.rental_company_name} />
          <div className="flex flex-col min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-bold text-white/90 truncate">Pickup {v.vehicle_name ? `${v.vehicle_name}` : 'car'} from {d.rental_company_name}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-white/60 mt-0.5 min-w-0">
              <span className="truncate" title={d.pickup_location_name}>{d.pickup_location_name}</span>
              <Dot className="hidden sm:inline-block" />
              <span className="hidden sm:inline">{formatClockTime(d.pickup_time)}</span>
            </div>
          </div>
          <div className="flex flex-col items-center gap-1 shrink-0 sm:w-[6rem]">
            <div className="flex items-center gap-1 shrink-0 justify-center">
              <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-sm font-semibold text-white/90">{(d.cost || 0).toFixed(2)}</span>
            </div>
          </div>
        </>
      }
      expandedContent={
        <div className="pt-3 space-y-4">
          {/* Vehicle block */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/40 mb-2">Vehicle</div>
            <div className="text-sm font-semibold text-white/85 mb-2">{v.vehicle_name}</div>
            <div className="flex flex-wrap items-center gap-2">
              {v.vehicle_transmission && v.vehicle_transmission.toLowerCase() !== 'n/a' && <Chip>{v.vehicle_transmission}</Chip>}
              {typeof v.vehicle_seats === 'number' && <Chip>{v.vehicle_seats} Seats</Chip>}
              {typeof v.vehicle_doors === 'number' && <Chip>{v.vehicle_doors} Doors</Chip>}
              {v.fuel_type && v.fuel_type.toLowerCase() !== 'n/a' && <Chip>{v.fuel_type}</Chip>}
              {v.mileage && v.mileage.toLowerCase() !== 'n/a' && <Chip>{v.mileage}</Chip>}
              {v.group && v.group.toLowerCase() !== 'n/a' && <Chip>{v.group}</Chip>}
              {typeof v.airbags === 'boolean' && v.airbags === true && <Chip>Airbags</Chip>}
              {typeof v.free_cancellation === 'boolean' && v.free_cancellation === true && <Chip>Free Cancellation</Chip>}
            </div>
          </div>

          {/* Pickup block */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/40 mb-2">Pickup</div>
            <div className="flex items-start gap-2 text-xs text-white/75">
              <MapPin className="w-3.5 h-3.5 text-cyan/70 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white/85">{d.pickup_location_name}</div>
                {d.pickup_location_address && <div className="text-white/60">{d.pickup_location_address}</div>}
              </div>
            </div>
          </div>

          {d.pickup_instructions && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Instructions</div>
              <p className="text-xs text-white/75 leading-relaxed whitespace-pre-line">{d.pickup_instructions}</p>
            </div>
          )}

          <TipsSection title="Pickup Tips" tips={d.pickup_tips} />

          {isValidUrl(d.booking_url) && (
            <a
              href={d.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan hover:text-cyan-200 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Book Rental
            </a>
          )}
        </div>
      }
    />
  );
}
