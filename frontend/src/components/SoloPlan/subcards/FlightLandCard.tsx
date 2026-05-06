import { Plane } from 'lucide-react';
import SubCardShell from './common/SubCardShell';
import TipsSection from './common/TipsSection';
import ViewOnMapButton from './common/ViewOnMapButton';
import LockToggle from './common/LockToggle';
import { EVENT_ACCENT, EVENT_ICON, EVENT_LABEL, formatClockTime, isValidUrl } from '../constants';
import { Dot } from '../Atoms';

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
        className="w-8 h-8 rounded-md bg-white object-contain p-1 shrink-0"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />
    );
  }
  return (
    <div className="w-8 h-8 flex items-center justify-center shrink-0 rounded-md bg-white">
      <Plane className="w-4 h-4 text-black" />
    </div>
  );
}

export default function FlightLandCard({ event, onViewOnMap, onToggleLock, contentKey }: Props) {
  const d = event?.flight_land_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.FLIGHT_LAND;
  const Icon = EVENT_ICON.FLIGHT_LAND;

  return (
    <SubCardShell
      eventType="FLIGHT_LAND"
      label={EVENT_LABEL.FLIGHT_LAND}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      lockButton={onToggleLock ? <LockToggle isLocked={event?.is_locked === true} onToggle={onToggleLock} /> : undefined}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      collapsedContent={
        <>
          <LogoOrIcon url={d.airline_logo_url} name={d.airline} />
          <div className="flex flex-col min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-bold text-white/90 truncate">{d.airline}</span>
            </div>
            <span className="text-[10px] text-white/40 tracking-widest uppercase hidden md:inline">
                {d.flight_number}
              </span>
            <div className="flex items-center gap-2 text-xs text-white/70 mt-0.5">
              <span className="font-bold tracking-wider">To {d.arrival_airport_code}</span>
              <Dot />
              <span>{formatClockTime(d.arrival_time)}</span>
            </div>
          </div>
        </>
      }
      expandedContent={
        <div className="pt-3">
            <div className="text-[10px] uppercase tracking-wider text-white/40 mb-2">Arrival Airport</div>
            <div className="flex items-start gap-2 text-xs text-white/75">
              <div>
                <div className="font-semibold text-white/85">{d.arrival_airport_name}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-white/60 justify-center mt-1">
            <span className="font-semibold text-white/80">{d.airline}</span>
            <Dot />
            <span className="font-mono tracking-wider">{d.flight_number}</span>
          </div>
          <TipsSection title="Landing Tips" tips={d.landing_tips} />
        </div>
      }
    />
  );
}
