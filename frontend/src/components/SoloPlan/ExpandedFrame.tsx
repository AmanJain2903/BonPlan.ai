import { ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import PlacesPolaroid from './PlacesPolaroid';
import {
  Calendar,
  Activity,
  DollarSign,
  Navigation,
  Loader2,
  AlertTriangle,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { ItineraryDay } from './types';
import { EASE_OUT_EXPO, formatDateForDayCard, formatMiles, metersFromCommutes } from './constants';

const VALUE_SWAP = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.25 },
};

interface ExpandedFrameProps {
  day: ItineraryDay;
  allDays: ItineraryDay[];
  onClose: () => void;
  onNavigate: (delta: -1 | 1) => void;
  destinations?: string[];
  /** Right-side action button in the header (e.g. Map / Back to Card toggle). */
  actionButton: ReactNode;
  /** Key identifying the currently rendered body, used to drive crossfade on view switches. */
  bodyKey: string;
  /** Body content: expanded subcard list or the map. */
  children: ReactNode;
}

/**
 * Shared frame for the ExpandedDayCard and DayMapView. Owns the outer styled
 * motion container, the header (close + nav + stats + status + action), and a
 * body slot. Swapping its children across view modes triggers a quick crossfade
 * inside AnimatePresence so the outer frame stays put.
 */
export default function ExpandedFrame({
  day,
  allDays,
  onClose,
  onNavigate,
  actionButton,
  bodyKey,
  children,
  destinations = [],
}: ExpandedFrameProps) {
  const isDefaultTitle = typeof day.title === 'string' && day.title.trim().toLowerCase() === `day ${day.dayNumber}`;
  const displayTitle = day.title && !isDefaultTitle ? day.title : `Day ${day.dayNumber}`;

  const frameClass = day.hasError
    ? 'bg-black/60 border border-red-500/40 shadow-[0_0_30px_rgba(239,68,68,0.15)]'
    : day.isLoading
      ? 'bg-black/60 border border-cyan/40 shadow-[0_0_30px_rgba(102,252,241,0.15)] glow-cyan'
      : 'bg-black/40 border border-cyan/20 shadow-2xl';

  const statusKey = day.hasError ? 'error' : day.isLoading ? 'loading' : 'done';
  const distanceMeters = metersFromCommutes(day.events);

  const currentIdx = allDays.findIndex((d) => d.dayNumber === day.dayNumber);
  const canPrev = currentIdx > 0;
  const canNext = currentIdx >= 0 && currentIdx < allDays.length - 1;

  return (
    <div
      className="relative w-full h-full"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.25 } }}
        transition={{ duration: 0.45, ease: EASE_OUT_EXPO }}
        className={`relative w-full h-full rounded-3xl backdrop-blur-md overflow-hidden flex flex-col ${frameClass}`}
      >
        {/* Ambient background polaroid — rotates through the day's place images */}
        <PlacesPolaroid day={day} variant="background" destinations={destinations} />

        {day.isLoading && !day.hasError && (
          <motion.div
            aria-hidden
            animate={{ opacity: [0.15, 0.45, 0.15] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute inset-0 bg-gradient-to-br from-cyan/15 via-transparent to-cyan/15 blur-sm pointer-events-none z-[1]"
          />
        )}

        {/* Header */}
        <div className="relative z-10 shrink-0 px-3 sm:px-6 pt-3 sm:pt-5 pb-2 sm:pb-4 border-b border-white/[0.06]">
          <div className="flex items-start gap-1.5 sm:gap-3">
            {/* Left: close */}
            <div className="flex items-center shrink-0 pt-0.5">
              <button
                onClick={onClose}
                className="p-1.5 sm:p-2 rounded-xl text-white/70 hover:text-white hover:bg-white/10 transition-all"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Center info */}
            <div className="flex-1 min-w-0">
              <h3 className="text-base sm:text-2xl font-bold tracking-tight text-white/90 truncate" title={displayTitle}>
                <AnimatePresence mode="wait">
                  <motion.span key={displayTitle} {...VALUE_SWAP} className="block truncate">
                    {displayTitle}
                  </motion.span>
                </AnimatePresence>
              </h3>
              <div className="flex flex-wrap items-center gap-1 sm:gap-2 mt-1 sm:mt-2">
                <AnimatePresence>
                  {day.date && (
                    <motion.div
                      key="date-pill"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.25 }}
                      className="flex items-center gap-1 sm:gap-1.5 text-cyan/80 bg-cyan/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-full"
                    >
                      <Calendar className="w-3 sm:w-3.5 h-3 sm:h-3.5 shrink-0" />
                      <span className="text-[9px] sm:text-[10px] font-semibold uppercase tracking-wider">
                        {formatDateForDayCard(day.date)}
                      </span>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="flex items-center gap-1 sm:gap-1.5 text-white/70 bg-white/[0.04] border border-white/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-full">
                  <Activity className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-cyan" />
                  <span className="text-[9px] sm:text-[11px] font-semibold">
                    {day.eventsCount} {day.eventsCount === 1 ? 'Activity' : 'Activities'}
                  </span>
                </div>

                <div className="flex items-center gap-0.5 sm:gap-1 text-white/70 bg-white/[0.04] border border-white/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-full">
                  <DollarSign className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-emerald-400" />
                  <span className="text-[9px] sm:text-[11px] font-semibold">
                    {day.cost.toFixed(2)}
                  </span>
                </div>

                <div className="flex items-center gap-1 sm:gap-1.5 text-white/70 bg-white/[0.04] border border-white/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-full">
                  <Navigation className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-cyan" />
                  <span className="text-[9px] sm:text-[11px] font-semibold">
                    {formatMiles(distanceMeters)}
                  </span>
                </div>

                <AnimatePresence mode="wait">
                  <motion.div
                    key={statusKey}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-center"
                  >
                    {statusKey === 'error' ? (
                      <AlertTriangle className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-red-400" />
                    ) : statusKey === 'loading' ? (
                      <Loader2 className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-cyan animate-spin" />
                    ) : null}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>

            {/* Right controls */}
            <div className="shrink-0 flex flex-col items-center gap-0.5">
              {actionButton}
              <div className="flex items-center gap-1 justify-center">
                <button
                  onClick={() => canPrev && onNavigate(-1)}
                  disabled={!canPrev}
                  className={`p-1.5 sm:p-2 rounded-xl transition-all ${canPrev ? 'text-cyan hover:bg-cyan/10' : 'text-white/20 cursor-not-allowed'}`}
                  title="Previous day"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => canNext && onNavigate(1)}
                  disabled={!canNext}
                  className={`p-1.5 sm:p-2 rounded-xl transition-all ${canNext ? 'text-cyan hover:bg-cyan/10' : 'text-white/20 cursor-not-allowed'}`}
                  title="Next day"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Body slot with crossfade between expanded and map content. The body
            container is always overflow-hidden; each body component (ExpandedDayCardBody
            / DayMapViewBody) owns its own scroll when needed. */}
        <div className="relative z-10 flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={bodyKey}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="relative w-full h-full"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan/5 via-transparent to-transparent pointer-events-none" />
      </motion.div>
    </div>
  );
}
