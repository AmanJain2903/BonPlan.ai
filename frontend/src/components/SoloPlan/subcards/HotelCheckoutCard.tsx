import { MapPin, BedSingle } from 'lucide-react';
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
        className="w-8 h-8 rounded-md bg-white/80 object-contain p-1 shrink-0"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />
    );
  }
  return (
    <div className="w-8 h-8 flex items-center justify-center shrink-0 rounded-md bg-white">
      <BedSingle className="w-4 h-4 text-black" />
    </div>
  );
}

export default function HotelCheckoutCard({ event, onViewOnMap, contentKey }: Props) {
  const d = event?.hotel_checkout_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.HOTEL_CHECKOUT;
  const Icon = EVENT_ICON.HOTEL_CHECKOUT;

  return (
    <SubCardShell
      eventType="HOTEL_CHECKOUT"
      label={EVENT_LABEL.HOTEL_CHECKOUT}
      Icon={Icon}
      accent={accent}
      contentKey={contentKey}
      viewOnMapButton={<ViewOnMapButton onClick={onViewOnMap} />}
      collapsedContent={
        <>
          <LogoOrIcon url={d.hotel_logo_url} name={d.hotel_name} />
          <div className="flex flex-col min-w-0 flex-1">
            <span className="text-sm font-bold text-white/90 truncate" title={d.hotel_name}>
              {d.hotel_name}
            </span>
            <div className="flex items-center gap-2 text-xs text-white/60 mt-0.5">
              <span>Check-out</span>
              <Dot />
              <span>{formatClockTime(d.checkout_time)}</span>
            </div>
          </div>
        </>
      }
      expandedContent={
        <div className="pt-3 space-y-3">
          {d.address && (
            <div className="flex items-start gap-2 text-xs text-white/70">
              <MapPin className="w-3.5 h-3.5 text-cyan/70 shrink-0 mt-0.5" />
              <span>{d.address}</span>
            </div>
          )}
          {d.checkout_rules && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Check-out Rules</div>
              <p className="text-xs text-white/75 leading-relaxed whitespace-pre-line">{d.checkout_rules}</p>
            </div>
          )}
          <TipsSection title="Check-out Tips" tips={d.checkout_tips} />
        </div>
      }
    />
  );
}
