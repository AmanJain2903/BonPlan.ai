import { MapPin } from 'lucide-react';

interface ViewOnMapButtonProps {
  onClick: () => void;
  label?: string;
}

export default function ViewOnMapButton({ onClick }: ViewOnMapButtonProps) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-white/60 hover:text-cyan hover:scale-120 transition-all"
    >
      <MapPin className="w-3.5 h-3.5 text-cyan/70" />
    </button>
  );
}
