import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Car, Footprints, Bike, Train, DollarSign } from 'lucide-react';
import { EASE_OUT_EXPO, formatDurationEnglish, formatMiles, isValidUrl } from '../constants';

interface Props {
  event: any;
  contentKey?: string | number;
}

const MODE_META: Record<string, { Icon: any; label: string; color: string; bg: string; border: string }> = {
  DRIVE: { Icon: Car, label: 'Drive', color: 'text-cyan-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/40' },
  WALK: { Icon: Footprints, label: 'Walk', color: 'text-cyan-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/40' },
  BICYCLE: { Icon: Bike, label: 'Bike', color: 'text-cyan-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/40' },
  TRANSIT: { Icon: Train, label: 'Transit', color: 'text-cyan-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/40' },
  TWO_WHEELER: { Icon: Bike, label: 'Two-Wheeler', color: 'text-cyan-200', bg: 'bg-cyan-400/10', border: 'border-cyan-400/40' },
};

const POPOVER_WIDTH_PX = 256; // w-64
const POPOVER_ESTIMATED_HEIGHT_PX = 140;

function findScrollParent(node: HTMLElement | null): HTMLElement | null {
  let cur: HTMLElement | null = node?.parentElement ?? null;
  while (cur) {
    const style = window.getComputedStyle(cur);
    const overflowY = style.overflowY;
    if (overflowY === 'auto' || overflowY === 'scroll') return cur;
    cur = cur.parentElement;
  }
  return null;
}

export default function CommuteConnector({ event, contentKey }: Props) {
  const d = event?.commute_details;
  const [tipsOpen, setTipsOpen] = useState(false);
  const [placement, setPlacement] = useState<{ vertical: 'below' | 'above'; horizontal: 'left' | 'right' }>({
    vertical: 'below',
    horizontal: 'left',
  });
  const containerRef = useRef<HTMLDivElement>(null);

  const recomputePlacement = () => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const scrollParent = findScrollParent(el);
    const scrollRect = scrollParent?.getBoundingClientRect();
    const bottomBound = scrollRect ? scrollRect.bottom : window.innerHeight;
    const rightBound = scrollRect ? scrollRect.right : window.innerWidth;
    const leftBound = scrollRect ? scrollRect.left : 0;

    const spaceBelow = bottomBound - rect.bottom;
    const vertical: 'below' | 'above' = spaceBelow < POPOVER_ESTIMATED_HEIGHT_PX + 16 ? 'above' : 'below';

    // Horizontal: anchor to left by default. Flip to right when popover would overflow the right edge.
    const spaceRight = rightBound - rect.left;
    const horizontal: 'left' | 'right' = spaceRight < POPOVER_WIDTH_PX + 16 && rect.right - leftBound >= POPOVER_WIDTH_PX
      ? 'right'
      : 'left';

    setPlacement({ vertical, horizontal });
  };

  useLayoutEffect(() => {
    recomputePlacement();
  }, []);

  useEffect(() => {
    if (!tipsOpen) return;
    recomputePlacement();
    const handler = () => recomputePlacement();
    window.addEventListener('resize', handler);
    window.addEventListener('scroll', handler, true);
    return () => {
      window.removeEventListener('resize', handler);
      window.removeEventListener('scroll', handler, true);
    };
  }, [tipsOpen]);

  if (!d) return null;

  const mode = MODE_META[d.travel_mode] || MODE_META.DRIVE;
  const ModeIcon = mode.Icon;
  const clickable = isValidUrl(d.maps_url);

  const onOpenMaps = () => {
    if (clickable) window.open(d.maps_url, '_blank', 'noopener,noreferrer');
  };

  const verticalClass = placement.vertical === 'above' ? 'bottom-full mb-2' : 'top-full mt-2';
  const horizontalClass = placement.horizontal === 'right' ? 'right-0' : 'left-0';

  return (
    <motion.div
      layout
      ref={containerRef}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
      className={`relative w-full group ${tipsOpen ? 'z-40' : 'z-0'}`}
    >
      <div
        role={clickable ? 'button' : undefined}
        tabIndex={clickable ? 0 : -1}
        onClick={clickable ? onOpenMaps : undefined}
        onKeyDown={(e) => {
          if (!clickable) return;
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onOpenMaps();
          }
        }}
        className={`relative mx-auto w-full max-w-sm rounded-xl px-4 py-2 flex items-stretch gap-4 z-10 transition-transform ${clickable ? 'cursor-pointer hover:scale-105' : ''}`}
      >
        {/* Left column: stats */}
        <AnimatePresence mode="wait">
          <motion.div
            key={contentKey ?? 'stable'}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -3 }}
            transition={{ duration: 0.25 }}
            className="flex flex-col justify-center gap-0.5 min-w-0 flex-1 text-right"
          >
            <span className="text-xs font-semibold text-white/80">{formatMiles(d.distanceMeters || 0)}</span>
            <span className="text-[11px] text-white/55">{d.durationSeconds && d.durationSeconds > 0 ? formatDurationEnglish(d.durationSeconds || 0) : ''}</span>
          </motion.div>
        </AnimatePresence>

        {/* Center column: vertical dashed line with mode icon */}
        <div className="relative flex flex-col items-center justify-center shrink-0 w-10">
          <div className={`absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[2px] ${mode.bg} rounded-full`}>
            <div className={`w-full h-full border-l-2 border-dashed ${mode.border}`} />
          </div>
          <div onMouseEnter={() => setTipsOpen(true)}
            onMouseLeave={() => setTipsOpen(false)}
            className={`relative z-10 w-9 h-9 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform`}
          >
            <ModeIcon className={`w-4 h-4 ${mode.color}`} />
            <AnimatePresence>
              {tipsOpen && d.commute_tips && (
                <motion.div
                  initial={{ opacity: 0, y: placement.vertical === 'above' ? 4 : -4, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: placement.vertical === 'above' ? 4 : -4, scale: 0.96, transition: { duration: 0.18 } }}
                  transition={{ duration: 0.18 }}
                  className={`absolute z-50 w-64 p-3 ${verticalClass} ${horizontalClass} rounded-xl bg-carbon/95 border border-cyan/25 shadow-xl backdrop-blur-xl pointer-events-none`}
                >
                  <div className="text-[10px] uppercase tracking-wider text-cyan/80 font-bold mb-1">Click to open Google Maps</div>
                  <p className="text-xs text-white/80 leading-relaxed whitespace-pre-line">{d.commute_tips}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Right column: mode label + optional transit fare */}
        <AnimatePresence mode="wait">
          <motion.div
            key={contentKey ?? 'stable'}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -3 }}
            transition={{ duration: 0.25 }}
            className="flex flex-col justify-center gap-1 min-w-0 flex-1"
          >
            <span className={`text-[10px] uppercase tracking-widest font-bold ${mode.color}`}>{mode.label}</span>
            {d.transit_fare !== undefined && d.transit_fare !== null && d.transit_fare > 0 && (
              <span className="text-[11px] text-emerald-300 flex items-center justify-start">
                <DollarSign className="w-3 h-3" />
                {d.transit_fare.toFixed(2)}
              </span>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
