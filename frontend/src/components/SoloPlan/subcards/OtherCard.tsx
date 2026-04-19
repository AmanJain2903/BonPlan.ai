import { DollarSign, MapPin, ExternalLink, Sparkles } from 'lucide-react';
import SubCardShell from './common/SubCardShell';
import TipsSection from './common/TipsSection';
import ViewOnMapButton from './common/ViewOnMapButton';
import { Dot } from '../Atoms';
import { EVENT_ACCENT, EVENT_ICON, EVENT_LABEL, formatClockTime, formatDurationEnglish, isValidUrl } from '../constants';

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
        className="w-8 h-8 rounded-md bg-white/80 object-contain p-1 shrink-0"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />
    );
  }
  return (
    <div className="w-8 h-8 flex items-center justify-center shrink-0 rounded-md bg-white">
      <Sparkles className="w-4 h-4 text-black" />
    </div>
  );
}

export default function OtherCard({ event, onViewOnMap, contentKey }: Props) {
  const d = event?.other_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.OTHER;
  const Icon = EVENT_ICON.OTHER;

  const duration = formatDurationEnglish((d.durationMinutes || 0) * 60, d.start_time, d.end_time);

  return (
    <SubCardShell
      eventType="OTHER"
      label={EVENT_LABEL.OTHER}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      collapsedContent={
        <>
          <LogoOrIcon url={d.logo_url} name={d.location} />
          <div className="flex flex-col min-w-0 flex-1">
            <span className="text-sm font-bold text-white/90 truncate" title={d.event_name}>
              {d.event_name}
            </span>
            {d.location && (
              <span className="text-[11px] text-white/50 truncate">{d.location}</span>
            )}
            <div className="flex items-center gap-2 text-[11px] text-white/60 mt-0.5">
              <span>{formatClockTime(d.start_time)} {duration && `– ${formatClockTime(d.end_time)}`}</span>
              {duration && <><Dot /> {duration}</>}
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
              <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Details</div>
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
