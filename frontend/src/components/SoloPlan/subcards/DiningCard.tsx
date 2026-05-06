import { DollarSign, Star, MapPin, ExternalLink, UtensilsCrossed } from 'lucide-react';
import SubCardShell from './common/SubCardShell';
import TipsSection from './common/TipsSection';
import ViewOnMapButton from './common/ViewOnMapButton';
import LockToggle from './common/LockToggle';
import { EVENT_ACCENT, EVENT_ICON, EVENT_LABEL, formatClockTime, formatDurationEnglish, isValidUrl } from '../constants';

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
      <UtensilsCrossed className="w-4 h-4 text-black" />
    </div>
  );
}

export default function DiningCard({ event, onViewOnMap, onToggleLock, contentKey }: Props) {
  const d = event?.place_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.DINING;
  const Icon = EVENT_ICON.DINING;

  const duration = formatDurationEnglish((d.durationMinutes || 0) * 60, d.start_time, d.end_time);

  return (
    <SubCardShell
      eventType="DINING"
      label={EVENT_LABEL.DINING}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      lockButton={onToggleLock ? <LockToggle isLocked={event?.is_locked === true} onToggle={onToggleLock} /> : undefined}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      startTime={d.start_time}
      endTime={d.end_time}
      collapsedContent={
        <>
          <LogoOrIcon url={d.logo_url} name={d.place_name} />
          <div className="flex flex-col min-w-0 flex-1">
            <span className="text-sm font-bold text-white/90 truncate" title={d.event_name}>
              {d.event_name}
            </span>
            {d.place_name && (
              <span className="text-[11px] text-white/50 truncate">{d.place_name}</span>
            )}
            <div className="mt-0.5 text-[10px] sm:text-[11px] text-white/60 leading-tight">
              <span className="whitespace-nowrap">{formatClockTime(d.start_time)}{duration ? ` – ${formatClockTime(d.end_time)}` : ''}</span>
              {duration && <span className="whitespace-nowrap"> · {duration}</span>}
            </div>
          </div>
          <div className="flex flex-col items-center gap-1 shrink-0 sm:w-[6rem]">
            <div className="flex items-center gap-1 shrink-0 justify-center">
              <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-sm font-semibold text-white/90">{(d.cost || 0).toFixed(2)}</span>
            </div>
            {typeof d.rating === 'number' && d.rating > 0 && (
              <div className="hidden sm:flex items-center gap-1 shrink-0 px-2 py-0.5 justify-center">
                <Star className="w-3 h-3 text-amber-300 fill-amber-300" />
                <span className="text-[12px] font-semibold text-amber-200">{d.rating.toFixed(1)}</span>
              </div>
            )}
          </div>
        </>
      }
      expandedContent={
        <div className="pt-3 space-y-3">
          {d.summary && <p className="text-xs text-white/75 leading-relaxed">{d.summary}</p>}
          {d.address && (
            <div className="flex items-start gap-2 text-xs text-white/70">
              <MapPin className="w-3.5 h-3.5 text-cyan/70 shrink-0 mt-0.5" />
              <span>{d.address}</span>
            </div>
          )}
          {d.event_description && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">About the Visit</div>
              <p className="text-xs text-white/75 leading-relaxed">{d.event_description}</p>
            </div>
          )}
          <TipsSection tips={d.event_tips} />
          {(isValidUrl(d.website_url) || isValidUrl(d.google_maps_url)) && (
            <div className="flex items-center gap-4 pt-1">
              {isValidUrl(d.website_url) && (
                <a
                  href={d.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan hover:text-cyan-200 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Website
                </a>
              )}
              {isValidUrl(d.google_maps_url) && (
                <a
                  href={d.google_maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan hover:text-cyan-200 transition-colors"
                >
                  <MapPin className="w-3.5 h-3.5" /> Google Maps
                </a>
              )}
            </div>
          )}
        </div>
      }
    />
  );
}
