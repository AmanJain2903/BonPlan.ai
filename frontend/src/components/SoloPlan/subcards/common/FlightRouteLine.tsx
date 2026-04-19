import { formatClockTime, formatDurationEnglish } from '../../constants';

export interface FlightStop {
  code: string;
  name: string;
  timeIso?: string;
  layoverMinutes?: number;
}

interface FlightRouteLineProps {
  stops: FlightStop[];
}

/**
 * Horizontal rail: first stop aligned left, last stop aligned right, any middle
 * stops evenly distributed (proportional positioning is visually equivalent for
 * small stop counts and keeps labels readable). Each stop shows code, name, time,
 * and for layovers the layover duration.
 */
export default function FlightRouteLine({ stops }: FlightRouteLineProps) {
  if (!stops || stops.length < 2) return null;

  const n = stops.length;
  return (
    <div className="w-full mt-2 mb-4 px-1">
      <div className="relative w-full">
        {/* Rail */}
        <div className="absolute left-2 right-2 top-1 h-[2px] bg-gradient-to-r from-cyan/50 via-cyan/30 to-cyan/50 rounded-full" />

        {/* Dots */}
        <div className="relative flex items-start justify-between">
          {stops.map((stop, i) => {
            const isEdge = i === 0 || i === n - 1;
            return (
              <div
                key={`${stop.code}-${i}`}
                className={`flex flex-col items-${i === 0 ? 'start' : i === n - 1 ? 'end' : 'center'} gap-2 flex-1 min-w-0 relative`}
                style={{ maxWidth: `${100 / n}%` }}
              >
                <div
                  className={`w-3 h-3 rounded-full border-2 shrink-0 z-10 ${
                    isEdge ? 'bg-cyan border-cyan shadow-[0_0_10px_rgba(102,252,241,0.6)]' : 'bg-black border-cyan/60'
                  }`}
                />
                <div
                  className={`flex flex-col items-${i === 0 ? 'start' : i === n - 1 ? 'end' : 'center'} text-center min-w-0 w-full px-1`}
                >
                  <span className="text-sm font-bold tracking-wider text-white/90">{stop.code}</span>
                  <span className="text-[10px] text-white/50 truncate max-w-full" title={stop.name}>
                    {stop.name}
                  </span>
                  {stop.timeIso && (
                    <span className="text-[10px] text-cyan/80 font-semibold mt-0.5">{formatClockTime(stop.timeIso)}</span>
                  )}
                  {!isEdge && typeof stop.layoverMinutes === 'number' && stop.layoverMinutes > 0 && (
                    <span className="text-[9px] text-white/40 mt-0.5 uppercase tracking-wider flex items-center gap-1 justify-center">
                      {formatDurationEnglish(stop.layoverMinutes * 60)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
