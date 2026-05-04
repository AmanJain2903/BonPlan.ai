import { DollarSign, Star, MapPin, BedDouble, ExternalLink } from 'lucide-react';
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
      <BedDouble className="w-4 h-4 text-black" />
    </div>
  );
}

export default function HotelCheckinCard({ event, onViewOnMap, contentKey }: Props) {
  const d = event?.hotel_checkin_details;
  if (!d) return null;

  const accent = EVENT_ACCENT.HOTEL_CHECKIN;
  const Icon = EVENT_ICON.HOTEL_CHECKIN;

  return (
    <SubCardShell
      eventType="HOTEL_CHECKIN"
      label={EVENT_LABEL.HOTEL_CHECKIN}
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
              <span>Check-in</span>
              <Dot />
              <span>{formatClockTime(d.checkin_time)}</span>
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
        <div className="pt-3 space-y-4">
          {typeof d.rating === 'number' && d.rating > 0 && (
            <p className="text-xs text-white/75 leading-relaxed">Rating: {d.rating.toFixed(1)}/10</p>
          )}
          {d.address && (
            <div className="flex items-start gap-2 text-xs text-white/70">
              <MapPin className="w-3.5 h-3.5 text-cyan/70 shrink-0 mt-0.5" />
              <span>{d.address}</span>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            {typeof d.nbRooms === 'number' && d.nbRooms > 0 && (
              <span className="px-2 py-1 rounded-full bg-white/[0.04] border border-cyan/30 text-white/75">
                {d.nbRooms} {d.nbRooms === 1 ? 'Room' : 'Rooms'}
              </span>
            )}
            {typeof d.nbAdults === 'number' && d.nbAdults > 0 && (
              <span className="px-2 py-1 rounded-full bg-white/[0.04] border border-cyan/30 text-white/75">
                {d.nbAdults} {d.nbAdults === 1 ? 'Adult' : 'Adults'}
              </span>
            )}
            {typeof d.nbChildren === 'number' && d.nbChildren > 0 && d.nbChildren > 0 && (
              <span className="px-2 py-1 rounded-full bg-white/[0.04] border border-cyan/30 text-white/75">
                {d.nbChildren} {d.nbChildren === 1 ? 'Child' : 'Children'}
              </span>
            )}
            {typeof d.stayLengthInDays === 'number' && d.stayLengthInDays > 0 && (
              <span className="px-2 py-1 rounded-full bg-white/[0.04] border border-cyan/30 text-white/75">
                {d.stayLengthInDays} {d.stayLengthInDays === 1 ? 'Night' : 'Nights'}
              </span>
            )}
          </div>
          {d.reviews_summary && (
            <div className="mt-1">
              <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Reviews</div>
              <p className="text-xs text-white/75 leading-relaxed">{d.reviews_summary}</p>
            </div>
          )}
          <TipsSection title="Check-in Tips" tips={d.checkin_tips} />
          {isValidUrl(d.booking_url) && (
            <a
              href={d.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan hover:text-cyan-200 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Book Hotel
            </a>
          )}
        </div>
      }
    />
  );
}
