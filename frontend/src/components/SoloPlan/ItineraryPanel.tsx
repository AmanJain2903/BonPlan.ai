import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Info, ArrowRight, ArrowDown, AlertTriangle, OctagonX, RefreshCw, Play } from 'lucide-react';
import { EASE_OUT_EXPO, SHIMMER_WIDTHS } from './constants';
import { ItineraryState } from './types';
import DayCard from './DayCard';

interface ItineraryPanelProps {
  isChatMinimized: boolean;
  planStatus: string;
  itineraryState: ItineraryState;
  errorType?: 'stopped' | 'error' | null;
  onRetry?: () => void;
}

export default function ItineraryPanel({
  isChatMinimized,
  planStatus,
  itineraryState,
  errorType,
  onRetry,
}: ItineraryPanelProps) {
  const [showTips, setShowTips] = useState(false);
  const tipsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showTips) return;
    const handler = (e: MouseEvent) => {
      if (tipsRef.current && !tipsRef.current.contains(e.target as Node)) {
        setShowTips(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showTips]);

  const isGenerating = planStatus === 'GENERATING';
  const hasStarted = itineraryState.hasStarted && itineraryState.days.length > 0;
  const hasDayCards = hasStarted && itineraryState.days.some((d) => d.events.length > 0);

  return (
    <motion.div
      key="itinerary-panel"
      layout
      initial={{ opacity: 0, width: 0, x: -30 }}
      animate={{
        opacity: 1,
        width: isChatMinimized ? '100%' : '70%',
        x: 0,
      }}
      exit={{ opacity: 0, transition: { duration: 0.3  } }}
      transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
      className="flex-shrink-0 flex flex-col bg-carbon/40 border border-white/[0.06] rounded-3xl overflow-hidden"
    >
      <div
        className={`flex-1 flex flex-col items-center px-10 py-8 relative w-full overflow-y-auto ${
          (!hasStarted || (errorType && !hasDayCards)) ? 'justify-center' : 'justify-start'
        }`}
      >
        {/* Trip tips button */}
        {hasStarted && itineraryState.tripTips && itineraryState.tripTips.length > 0 && (
          <div ref={tipsRef} className="absolute top-4 right-4 z-40 flex flex-col items-end">
            <button
              onClick={() => setShowTips(!showTips)}
              className={`p-2 rounded-full transition-colors group ${
                showTips ? 'bg-cyan text-black' : 'text-cyan hover:bg-cyan/20'
              }`}
              title="Trip Tips"
            >
              <Info className="w-5 h-5" />
            </button>
            <AnimatePresence>
              {showTips && (
                <motion.div
                  initial={{ opacity: 0, y: -10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95, transition: { duration: 0.3 } }}
                  transition={{ duration: 0.2 }}
                  className="mt-2 w-72 p-5 bg-carbon/90 border border-cyan/20 rounded-2xl shadow-2xl backdrop-blur-xl max-h-[60vh] overflow-hidden bg-gradient-to-t from-cyan/10 to-transparent"
                >
                  <h4 className="text-sm font-bold text-cyan mb-3 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    Trip Tips
                  </h4>
                  <ul className="space-y-3 max-h-[30vh] overflow-y-auto pr-1 scrollbar-hide">
                    {itineraryState.tripTips.map((tip, i) => (
                      <li key={i} className="text-xs text-white/80 leading-relaxed border-l-2 border-cyan/30 pl-3">
                        {tip}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Error/stopped state WITHOUT day cards rendered */}
        {errorType && !hasDayCards ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: EASE_OUT_EXPO }}
            className="flex flex-col items-center gap-5"
          >
            <div className="relative">
              {errorType === 'stopped' ? (
                <div className="w-20 h-20 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                  <OctagonX className="w-10 h-10 text-red-400" />
                </div>
              ) : (
                <div className="w-20 h-20 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                  <AlertTriangle className="w-10 h-10 text-red-400" />
                </div>
              )}
              <div className="absolute -inset-2 rounded-2xl bg-red-500/10 blur-xl animate-pulse" />
            </div>
            <div className="text-center">
              <h2 className="text-xl font-bold text-red-400 mb-1">
                {errorType === 'stopped' ? 'Execution Stopped' : 'Error Occurred'}
              </h2>
              <p className="text-sm text-white/40 mb-4">
                {errorType === 'stopped'
                  ? 'You stopped the generation.'
                  : 'Something went wrong during generation.'}
              </p>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="flex items-center gap-2 mx-auto text-cyan/70 hover:text-cyan transition-colors text-xs font-bold uppercase tracking-wider group"
                >
                  {errorType === 'stopped' ? (
                    <>
                      <Play className="w-4 h-4 group-hover:scale-110 transition-transform" />
                      <span>Resume</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" />
                      <span>Try Again</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </motion.div>
        ) : !hasStarted ? (
          <>
            {/* Pre-start / shimmer state */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
              className="flex flex-col items-center gap-4 mb-10"
            >
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl bg-cyan/10 border border-cyan/20 flex items-center justify-center">
                  <Sparkles className="w-7 h-7 text-cyan" />
                </div>
                {isGenerating && (
                  <div className="absolute -inset-1 rounded-2xl bg-cyan/10 blur-md animate-pulse" />
                )}
              </div>
              <div className="text-center">
                <h2 className="text-xl font-bold text-white mb-1">
                  {isGenerating ? 'Generating Itinerary' : 'Waiting to Start'}
                </h2>
                <p className="text-sm text-white/40">
                  {isGenerating
                    ? 'AI is planning your trip'
                    : 'Your itinerary will appear here'}
                </p>
              </div>
            </motion.div>

            <div className="w-full max-w-lg flex flex-col gap-3">
              {SHIMMER_WIDTHS.map((w, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + i * 0.1, duration: 0.4 }}
                  className={`h-3 rounded-full overflow-hidden ${isGenerating ? 'bg-white/[0.06]' : 'bg-white/[0.03]'}`}
                  style={{ width: `${w * 100}%` }}
                >
                  {isGenerating && (
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-transparent via-white/10 to-transparent"
                      animate={{ x: ['-100%', '200%'] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'linear', delay: i * 0.2 }}
                    />
                  )}
                </motion.div>
              ))}
            </div>
          </>
        ) : (
          /* Day cards grid */
          <div
            className="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-y-12 gap-x-12 relative pb-10 pt-4 max-w-5xl mx-auto"
          >
            {itineraryState.days.map((day, index) => (
              <div key={day.dayNumber} className={`relative flex flex-col h-full z-10 w-full ${(index === itineraryState.days.length - 1 && itineraryState.days.length % 2 !== 0) || itineraryState.days.length === 1 ? 'md:col-span-2 md:w-1/2 md:mx-auto' : ''}`}>
                <DayCard day={day} index={index} />

                {/* {index < itineraryState.days.length - 1 && index % 2 === 0 && itineraryState.days.length > 1 && (
                  <div className="hidden md:flex absolute top-1/2 -right-10 transform -translate-y-1/2 z-0 text-cyan/20">
                    <ArrowRight className="w-8 h-8" />
                  </div>
                )}

                {index < itineraryState.days.length - 1 && index % 2 !== 0 && itineraryState.days.length > 1 && (
                  <div className="hidden md:flex absolute -bottom-10 -left-10 z-0 text-cyan/20 w-10 h-10">
                    <svg
                      viewBox="0 0 100 100"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="w-full h-full"
                    >
                      <line x1="100" y1="0" x2="0" y2="100" />
                      <polyline points="50 100 0 100 0 50" />
                    </svg>
                  </div>
                )} */}

              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
