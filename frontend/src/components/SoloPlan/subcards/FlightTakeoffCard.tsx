import { DollarSign, Plane } from 'lucide-react';
import SubCardShell from './common/SubCardShell';
import TipsSection from './common/TipsSection';
import ViewOnMapButton from './common/ViewOnMapButton';
import FlightRouteLine, { FlightStop } from './common/FlightRouteLine';
import { Dot } from '../Atoms';
import { EVENT_ACCENT, EVENT_ICON, EVENT_LABEL, formatClockTime, isValidUrl } from '../constants';
import { ExternalLink } from 'lucide-react';

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
      <Plane className="w-4 h-4 text-black" />
    </div>
  );
}

export default function FlightTakeoffCard({ event, onViewOnMap, contentKey }: Props) {
  const d = event?.flight_takeoff_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.FLIGHT_TAKEOFF;
  const Icon = EVENT_ICON.FLIGHT_TAKEOFF;

  const layovers = ((d.layovers || []) as any[]).map((l) => ({
    code: l.airport_code,
    name: l.airport_name,
    layoverMinutes: l.durationMinutes,
  }));

  // Build stops: departure -> layovers -> arrival. Falls back to last layover
  // as tail stop for legacy events without the arrival_* fields.
  const stops: FlightStop[] = [
    {
      code: d.departure_airport_code || '—',
      name: d.departure_airport_name || '',
      timeIso: d.departure_time,
    },
  ];
  if (layovers.length > 0) {
    if (d.arrival_airport_code) {
      // middle layovers preserve the layoverMinutes badge
      stops.push(...layovers);
    } else {
      // legacy: promote last layover to arrival (drop its duration badge)
      stops.push(...layovers.slice(0, -1));
      const last = layovers[layovers.length - 1];
      stops.push({ code: last.code, name: last.name });
    }
  }
  if (d.arrival_airport_code) {
    stops.push({
      code: d.arrival_airport_code,
      name: d.arrival_airport_name || '',
      timeIso: d.arrival_time,
    });
  }

  return (
    <SubCardShell
      eventType="FLIGHT_TAKEOFF"
      label={EVENT_LABEL.FLIGHT_TAKEOFF}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      collapsedContent={
        <>
          <LogoOrIcon url={d.airline_logo_url} name={d.airline} />
          <div className="flex flex-col min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-bold text-white/90 truncate">{d.airline}</span>
              <span className="text-[10px] text-white/40 tracking-widest uppercase hidden md:inline">
                {d.flight_number}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-white/70 mt-0.5">
              <span className="font-bold tracking-wider">From {d.departure_airport_code}</span>
              <Dot />
              <span>{formatClockTime(d.departure_time)}</span>
            </div>
          </div>
          <div className="flex flex-col items-center gap-1 shrink-0 w-[6rem]">
            <div className="flex items-center gap-1 shrink-0 justify-center">
              <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-sm font-semibold text-white/90">{(d.cost || 0).toFixed(2)}</span>
            </div>
          </div>
        </>
      }
      expandedContent={
        <div className="pt-3 space-y-4">
          <FlightRouteLine stops={stops} />
          <div className="flex items-center gap-2 text-xs text-white/60 justify-center mt-1">
            <span className="font-semibold text-white/80">{d.airline}</span>
            <Dot />
            <span className="font-mono tracking-wider">{d.flight_number}</span>
          </div>
          <TipsSection title="Takeoff Tips" tips={d.takeoff_tips} />
          {isValidUrl(d.booking_url) && (
            <a
              href={d.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan hover:text-cyan-200 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Book Flight
            </a>
          )}
        </div>
      }
    />
  );
}
