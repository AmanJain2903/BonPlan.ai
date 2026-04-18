import { ItineraryDay } from './types';

export default function PlacesPolaroid({ day: _day }: { day: ItineraryDay }) {
  return (
    <div className="relative w-full h-full aspect-3/2 bg-white/5 border border-white/10 rounded-xl flex items-center justify-center backdrop-blur-sm overflow-hidden">
      <span className="text-white/30 text-xs font-semibold tracking-widest uppercase">
        Places Polaroid Placeholder
      </span>
    </div>
  );
}