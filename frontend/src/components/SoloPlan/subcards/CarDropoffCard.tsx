import { Car, MapPin } from 'lucide-react';
import SubCardShell from './common/SubCardShell';
import TipsSection from './common/TipsSection';
import ViewOnMapButton from './common/ViewOnMapButton';
import LockToggle from './common/LockToggle';
import { Dot } from '../Atoms';
import { EVENT_ACCENT, EVENT_ICON, EVENT_LABEL, formatClockTime, isValidUrl } from '../constants';

interface Props {
  event: any;
  onViewOnMap: () => void;
  onToggleLock?: () => void;
  contentKey?: string | number;
}

function LogoOrIcon({ url, name }: { url?: string; name: string }) {
  if (isValidUrl(url)) {
    return (
      <img
        src={url}
        alt={name}
        className="w-8 h-8 rounded-md bg-white/80 object-contain p-1 shrink-0"
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

export default function CarDropoffCard({ event, onViewOnMap, onToggleLock, contentKey }: Props) {
  const d = event?.car_dropoff_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.CAR_DROPOFF;
  const Icon = EVENT_ICON.CAR_DROPOFF;

  return (
    <SubCardShell
      eventType="CAR_DROPOFF"
      label={EVENT_LABEL.CAR_DROPOFF}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      lockButton={onToggleLock ? <LockToggle isLocked={event?.is_locked === true} onToggle={onToggleLock} /> : undefined}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      collapsedContent={
        <>
          <LogoOrIcon url={d.rental_company_logo_url} name={d.rental_company_name} />
          <div className="flex flex-col min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-bold text-white/90 truncate">{d.rental_company_name}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-white/60 mt-0.5 min-w-0">
              <span className="truncate" title={d.dropoff_location_name}>{d.dropoff_location_name}</span>
              <Dot className="hidden sm:inline-block" />
              <span className="hidden sm:inline">{formatClockTime(d.dropoff_time)}</span>
            </div>
          </div>
        </>
      }
      expandedContent={
        <div className="pt-3 space-y-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-white/40 mb-2">Drop-off</div>
            <div className="flex items-start gap-2 text-xs text-white/75">
              <MapPin className="w-3.5 h-3.5 text-cyan/70 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white/85">{d.dropoff_location_name}</div>
                {d.dropoff_location_address && <div className="text-white/60">{d.dropoff_location_address}</div>}
                <div className="text-white/50 mt-0.5">At {formatClockTime(d.dropoff_time)}</div>
              </div>
            </div>
          </div>

          {d.dropoff_instructions && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Instructions</div>
              <p className="text-xs text-white/75 leading-relaxed whitespace-pre-line">{d.dropoff_instructions}</p>
            </div>
          )}

          <TipsSection title="Drop-off Tips" tips={d.dropoff_tips} />
        </div>
      }
    />
  );
}
