import { ItineraryDay } from './types';

export default function PlacesPolaroid({ day: _day }: { day: ItineraryDay }) {
  return (
    <div className="w-full h-32 bg-white/5 border border-white/10 rounded-xl flex items-center justify-center backdrop-blur-sm">
      <span className="text-white/30 text-xs font-semibold tracking-widest uppercase">
        Polaroid Placeholder
      </span>
    </div>
  );
}
