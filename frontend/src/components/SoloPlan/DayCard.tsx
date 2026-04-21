import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ItineraryDay } from './types';
import { Calendar, DollarSign, Activity, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import PlacesPolaroid from './PlacesPolaroid';
import { formatDateForDayCard, EASE_OUT_EXPO } from './constants';

const VALUE_SWAP = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.25 },
};

interface DayCardProps {
  day: ItineraryDay;
  index?: number;
  onSelect?: (dayNumber: number) => void;
  hidden?: boolean;
}

export default function DayCard({ day, index = 0, onSelect, hidden = false }: DayCardProps) {
  const isDefaultTitle = typeof day.title === 'string' && day.title.trim().toLowerCase() === `day ${day.dayNumber}`;
  const displayTitle = day.title && !isDefaultTitle ? `${day.title}` : `Day ${day.dayNumber}`;

  // Track which lastUpdatedAt we have already "seen" so we only pulse for NEW updates.
  // The ref is updated in useEffect (after commit) — never during render — to avoid
  // Strict-Mode / concurrent-rendering issues where a second render call would
  // see the ref already updated and suppress the pulse.
  const seenUpdateRef = useRef<number | undefined>(day.lastUpdatedAt);
  const isNewUpdate = day.lastUpdatedAt != null
    && !day.isLoading
    && day.lastUpdatedAt !== seenUpdateRef.current;

  useEffect(() => {
    if (isNewUpdate) {
      seenUpdateRef.current = day.lastUpdatedAt;
    }
  }, [isNewUpdate, day.lastUpdatedAt]);

  const borderClass = day.hasError
    ? 'bg-black/60 border border-red-500/40 shadow-[0_0_30px_rgba(239,68,68,0.15)]'
    : day.isLoading
      ? 'bg-black/60 border border-cyan/40 shadow-[0_0_30px_rgba(102,252,241,0.15)] glow-cyan'
      : 'bg-black/40 border border-cyan/20 shadow-2xl hover:border-cyan/40';

  const statusKey = day.hasError ? 'error' : day.isLoading ? 'loading' : 'done';

  const handleClick = () => {
    if (onSelect) onSelect(day.dayNumber);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 0, scale: 0.97 }}
      animate={{ opacity: hidden ? 0 : 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay: index * 0.06, ease: EASE_OUT_EXPO }}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : -1}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (!onSelect) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
      className={`relative flex flex-col gap-5 p-6 h-full overflow-hidden rounded-3xl backdrop-blur-md transition-all duration-300 ${onSelect ? 'cursor-pointer hover:scale-[1.015]' : ''
        } ${hidden ? 'pointer-events-none' : ''} ${borderClass}`}
    >
      {day.isLoading && !day.hasError && (
        <motion.div
          animate={{ opacity: [0.2, 0.7, 0.2] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute inset-0 bg-gradient-to-br from-cyan/20 via-cyan/10 to-cyan/20 blur-sm pointer-events-none z-0"
        />
      )}

      <div className="flex items-start justify-between relative z-10 min-h-[4rem]">
        <div className="flex flex-col flex-1 min-w-0 pr-4">
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-white/90 truncate block max-w-full" title={displayTitle}>
            <AnimatePresence mode="wait">
              <motion.span key={displayTitle} {...VALUE_SWAP} className="block truncate">
                {displayTitle}
              </motion.span>
            </AnimatePresence>
          </h3>

          <div className="h-7 mt-2 flex items-center">
            <AnimatePresence>
              {day.date && (
                <motion.div
                  key={day.date}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.25 }}
                  className="flex items-center gap-1.5 text-cyan/70 bg-cyan/10 px-2.5 py-1 rounded-full w-fit"
                >
                  <Calendar className="w-3.5 h-3.5 shrink-0" />
                  <span className="text-xs font-semibold uppercase tracking-wider">{formatDateForDayCard(day.date)}</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <div className="flex-1 relative z-10">
        <PlacesPolaroid day={day} />
      </div>

      <div className="flex items-center gap-5 pt-5 border-t border-white/[0.08] relative z-10">
        <div className="flex items-center gap-2 text-white/60 hover:text-white/90 transition-colors">
          <Activity className="w-4 h-4 text-cyan" />
          <AnimatePresence mode="wait">
            <motion.span key={day.eventsCount} {...VALUE_SWAP} className="text-sm font-medium">
              {day.eventsCount} Activities
            </motion.span>
          </AnimatePresence>
        </div>
        <div className="flex items-center gap-1.5 text-white/60 hover:text-white/90 transition-colors">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          <AnimatePresence mode="wait">
            <motion.span key={day.cost} {...VALUE_SWAP} className="text-sm font-medium">
              ${day.cost.toFixed(2)}
            </motion.span>
          </AnimatePresence>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={statusKey}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.2 }}
            className="ml-auto flex items-center"
          >
            {statusKey === 'error' ? (
              <AlertTriangle className="w-5 h-5 text-red-400" />
            ) : statusKey === 'loading' ? (
              <Loader2 className="w-5 h-5 text-cyan animate-spin" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-cyan/70" />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan/5 via-transparent to-transparent pointer-events-none" />

      {/* Pulse animation: only fires for genuinely new / re-emitted updates */}
      <AnimatePresence>
        {isNewUpdate && (
          <motion.div
            key={`pulse-${day.lastUpdatedAt}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.8, ease: EASE_OUT_EXPO }}
            className="absolute inset-0 rounded-3xl pointer-events-none z-50 glow-cyan bg-gradient-to-br from-cyan/20 via-cyan/10 to-cyan/20"
            style={{
              boxShadow: '0 0 0 4px rgba(102, 252, 241, 0.5), 0 0 24px rgba(102, 252, 241, 0.25)',
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
