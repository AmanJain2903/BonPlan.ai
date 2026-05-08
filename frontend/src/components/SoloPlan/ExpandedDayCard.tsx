import { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import { ItineraryDay } from './types';
import { renderSubCardForEvent } from './subcards';
import PlaceholderSubCard from './subcards/PlaceholderSubCard';
import { EASE_OUT_EXPO, eventIdentityKey } from './constants';

interface ExpandedDayCardBodyProps {
  day: ItineraryDay;
  onViewOnMap: (event: any) => void;
  onToggleLock?: (event: any) => void;
  /** Direction of prev/next navigation, used to slide the list on day change. */
  navDirection?: 1 | -1;
}

const slideVariants = {
  enter: (dir: 1 | -1) => ({ opacity: 0, x: 24 * dir }),
  center: { opacity: 1, x: 0 },
  exit: (dir: 1 | -1) => ({ opacity: 0, x: -24 * dir, transition: { duration: 0.2 } }),
};

/**
 * Scrollable list of event subcards for a day. Renders the streaming placeholder
 * at the end while `day.isLoading && !day.hasError`. Day-to-day navigation from
 * the prev/next arrows slides the inner list only; the outer frame stays mounted.
 *
 * Each event subcard is keyed on (event_type + day + event_number + _updatedAt)
 * so that when the AI edits an event (potentially changing its type entirely),
 * the old card exits and the new card enters with a smooth crossfade.
 */
export default function ExpandedDayCardBody({ day, onViewOnMap, onToggleLock, navDirection = 1 }: ExpandedDayCardBodyProps) {
  const showPlaceholder = day.isLoading && !day.hasError;

  // Track which _updatedAt values were already present when the view opened
  // or when the day changed. Only pulse for values that appear AFTER mount.
  const seenUpdatesRef = useRef<Set<number>>(new Set());

  // On mount and whenever the day changes, snapshot all current _updatedAt values.
  useEffect(() => {
    const seen = new Set<number>();
    for (const ev of day.events || []) {
      if (ev?._updatedAt) seen.add(ev._updatedAt);
    }
    seenUpdatesRef.current = seen;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day.dayNumber]);

  return (
    <div className="w-full h-full overflow-y-auto px-5 py-5 scrollbar-hide">
      <AnimatePresence mode="wait" custom={navDirection}>
        <motion.div
          key={day.dayNumber}
          custom={navDirection}
          variants={slideVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
          className="max-w-3xl mx-auto w-full"
        >
          {day.events.length === 0 && !showPlaceholder && (
            <div className="h-full flex items-center justify-center text-center py-10">
              <div>
                {day.hasError ? (
                  <>
                    <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-2" />
                    <p className="text-sm text-white/60">This day didn&apos;t finish generating.</p>
                  </>
                ) : (
                  <p className="text-sm text-white/40">No events for this day yet.</p>
                )}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-3 w-full">
            <AnimatePresence initial={false}>
              {day.events.map((event: any) => {
                const stableKey = `${event.event_type}-${eventIdentityKey(event)}`;
                const updatedAt: number | undefined = event._updatedAt;

                // Only pulse if this _updatedAt value is genuinely new
                // (was not present when we opened this day / mounted).
                // Do NOT mutate the ref during render — that breaks in Strict Mode.
                const isNewUpdate = updatedAt != null && !seenUpdatesRef.current.has(updatedAt);

                return (
                  <motion.div
                    key={stableKey}
                    layout
                    className="relative"
                  >
                    {/* Update pulse: a brief cyan border glow that fades out
                        ONLY for genuinely re-emitted / edited events. */}
                    {isNewUpdate && (
                      <PulseOverlay updatedAt={updatedAt!} seenRef={seenUpdatesRef} />
                    )}
                    {renderSubCardForEvent(event, { onViewOnMap, onToggleLock })}
                  </motion.div>
                );
              })}

              {showPlaceholder && (
                <motion.div key={`placeholder-${day.dayNumber}`} layout>
                  <PlaceholderSubCard />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/**
 * Small helper component that marks an update as "seen" in useEffect (after commit)
 * rather than during render, preventing Strict-Mode double-render suppression.
 */
function PulseOverlay({
  updatedAt,
  seenRef,
}: {
  updatedAt: number;
  seenRef: React.MutableRefObject<Set<number>>;
}) {
  useEffect(() => {
    seenRef.current.add(updatedAt);
  }, [updatedAt, seenRef]);

  return (
    <motion.div
      key={`pulse-${updatedAt}`}
      initial={{ opacity: 1 }}
      animate={{ opacity: 0 }}
      transition={{ duration: 1.8, ease: 'easeOut' }}
      className="absolute inset-0 rounded-2xl pointer-events-none z-50"
      style={{
        boxShadow: '0 0 0 2px rgba(102, 252, 241, 0.5), 0 0 20px rgba(102, 252, 241, 0.2)',
      }}
    />
  );
}
