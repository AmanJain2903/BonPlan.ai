import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Info,
  AlertTriangle,
  OctagonX,
  RefreshCw,
  Play,
  Map as MapIcon,
  Activity,
  History,
} from 'lucide-react';
import { EASE_OUT_EXPO, SHIMMER_WIDTHS, eventKey } from './constants';
import { ItineraryState } from './types';
import type { ItinerarySnapshot } from '../../apis/plan';
import DayCard from './DayCard';
import ExpandedDayCardBody from './ExpandedDayCard';
import DayMapViewBody from './DayMapView';
import ExpandedFrame from './ExpandedFrame';
import GoogleMapsApiLoader from '../shared/GoogleMapsApiLoader.tsx';

interface ItineraryPanelProps {
  isChatMinimized: boolean;
  planStatus: string;
  itineraryState: ItineraryState;
  errorType?: 'stopped' | 'error' | null;
  onRetry?: () => void;
  onToggleLock?: (event: any) => void;
  snapshots?: ItinerarySnapshot[];
  snapshotCursor?: number;
  snapshotsLoading?: boolean;
  snapshotsError?: string;
  revertingSnapshot?: number | null;
  onOpenSnapshots?: () => void;
  onRevertSnapshot?: (versionIndex: number) => void;
}

export default function ItineraryPanel({
  isChatMinimized,
  planStatus,
  itineraryState,
  errorType,
  onRetry,
  onToggleLock,
  snapshots = [],
  snapshotCursor,
  snapshotsLoading = false,
  snapshotsError = '',
  revertingSnapshot = null,
  onOpenSnapshots,
  onRevertSnapshot,
}: ItineraryPanelProps) {
  const [showTips, setShowTips] = useState(false);
  const [showSnapshots, setShowSnapshots] = useState(false);
  const tipsRef = useRef<HTMLDivElement>(null);
  const snapshotsRef = useRef<HTMLDivElement>(null);

  // Expanded day + map overlay state
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'expanded' | 'map'>('expanded');
  const [highlightedEventKey, setHighlightedEventKey] = useState<string | null>(null);
  const [navDirection, setNavDirection] = useState<1 | -1>(1);

  // Pre-warm Google Maps libraries so the first Map toggle feels instant.
  useEffect(() => {
    const load = async () => {
      const g = (window as any).google;
      if (!g?.maps?.importLibrary) return;
      try {
        await Promise.all([
          g.maps.importLibrary('maps'),
          g.maps.importLibrary('marker'),
          g.maps.importLibrary('geometry'),
        ]);
      } catch {
        /* swallow */
      }
    };
    load();
    const id = setInterval(() => {
      const g = (window as any).google;
      if (g?.maps?.importLibrary) {
        clearInterval(id);
        load();
      }
    }, 250);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!showTips && !showSnapshots) return;
    const handler = (e: PointerEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (showTips && tipsRef.current && !tipsRef.current.contains(target)) {
        setShowTips(false);
      }
      if (showSnapshots && snapshotsRef.current && !snapshotsRef.current.contains(target)) {
        setShowSnapshots(false);
      }
    };
    document.addEventListener('pointerdown', handler, true);
    return () => document.removeEventListener('pointerdown', handler, true);
  }, [showTips, showSnapshots]);

  const isGenerating = planStatus === 'GENERATING';
  const hasStarted = itineraryState.hasStarted && itineraryState.days.length > 0;
  const hasDayCards = hasStarted && itineraryState.days.some((d) => d.events.length > 0);
  const displayedSnapshots = useMemo(
    () => [...snapshots].sort((a, b) => b.version_index - a.version_index),
    [snapshots],
  );

  const selectedDayData =
    selectedDay != null ? itineraryState.days.find((d) => d.dayNumber === selectedDay) || null : null;

  const handleCloseOverlay = useCallback(() => {
    setSelectedDay(null);
    setViewMode('expanded');
    setHighlightedEventKey(null);
  }, []);

  const handleNavigate = useCallback(
    (delta: -1 | 1) => {
      if (selectedDay == null) return;
      const idx = itineraryState.days.findIndex((d) => d.dayNumber === selectedDay);
      const next = idx + delta;
      if (next < 0 || next >= itineraryState.days.length) return;
      setNavDirection(delta);
      setSelectedDay(itineraryState.days[next].dayNumber);
      setHighlightedEventKey(null);
    },
    [selectedDay, itineraryState.days],
  );

  const handleOpenMap = useCallback((highlight?: string) => {
    setViewMode('map');
    setHighlightedEventKey(highlight ?? null);
  }, []);

  const handleBackToCard = useCallback(() => {
    setViewMode('expanded');
    setHighlightedEventKey(null);
  }, []);

  const handleViewOnMap = useCallback((event: any) => {
    setViewMode('map');
    setHighlightedEventKey(eventKey(event));
  }, []);

  /** Navigate to a different day while staying in map view (triggered by context marker clicks). */
  const handleNavigateToDay = useCallback(
    (dayNumber: number) => {
      const targetDay = itineraryState.days.find((d) => d.dayNumber === dayNumber);
      if (!targetDay) return;
      const curIdx = itineraryState.days.findIndex((d) => d.dayNumber === selectedDay);
      const newIdx = itineraryState.days.findIndex((d) => d.dayNumber === dayNumber);
      setNavDirection(newIdx > curIdx ? 1 : -1);
      setSelectedDay(dayNumber);
      setHighlightedEventKey(null);
      // Stay in map view
    },
    [itineraryState.days, selectedDay],
  );

  // Keyboard: Esc + arrow navigation while overlay is open
  useEffect(() => {
    if (selectedDay == null) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (viewMode === 'map') {
          handleBackToCard();
        } else {
          handleCloseOverlay();
        }
      } else if (e.key === 'ArrowLeft') {
        handleNavigate(-1);
      } else if (e.key === 'ArrowRight') {
        handleNavigate(1);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedDay, viewMode, handleBackToCard, handleCloseOverlay, handleNavigate]);

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
      exit={{ opacity: 0, transition: { duration: 0.3 } }}
      transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
      className="relative flex-shrink-0 flex flex-col bg-carbon/40 border border-white/[0.06] rounded-3xl overflow-hidden"
    >
      {/* Google Maps API preload (hidden, script-only). Keeps the Map toggle feeling instant. */}
      <GoogleMapsApiLoader solutionChannel="GMP_BonPlan_soloPlan" />

      {/* Fixed itinerary panel controls. The card grid scrolls underneath these on larger screens. */}
      {hasStarted && itineraryState.tripTips && itineraryState.tripTips.length > 0 && (
        <div ref={tipsRef} className="absolute top-1 right-1 z-50 flex flex-col items-end sm:top-1 sm:right-1">
          <button
            onClick={() => setShowTips(!showTips)}
            className={`p-2 rounded-full transition-colors group ${showTips ? 'bg-cyan text-black' : 'text-cyan hover:bg-cyan/20'
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

      {hasStarted && onOpenSnapshots && (
        <div ref={snapshotsRef} className="absolute top-1 left-1 z-50 flex flex-col items-start sm:top-1 sm:left-1">
          <button
            onClick={() => {
              const next = !showSnapshots;
              setShowSnapshots(next);
              if (next) onOpenSnapshots();
            }}
            className={`p-2 rounded-full transition-colors group ${showSnapshots ? 'bg-cyan text-black' : 'text-cyan hover:bg-cyan/20'
              }`}
            title="Version history"
          >
            <History className="w-5 h-5" />
          </button>
          <AnimatePresence>
            {showSnapshots && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95, transition: { duration: 0.3 } }}
                transition={{ duration: 0.2 }}
                className="mt-2 w-72 p-5 bg-carbon/90 border border-cyan/20 rounded-2xl shadow-2xl backdrop-blur-xl max-h-[60vh] overflow-hidden bg-gradient-to-t from-cyan/10 to-transparent"
              >
                <h4 className="text-sm font-bold text-cyan mb-3 flex items-center gap-2">
                  <History className="w-4 h-4" />
                  Versions
                </h4>

                {snapshotsLoading ? (
                  <div className="text-xs text-white/55 py-3">Loading versions...</div>
                ) : snapshotsError ? (
                  <div className="text-xs text-red-300/90 py-3">{snapshotsError}</div>
                ) : (
                  <div className="space-y-3 max-h-[30vh] overflow-y-auto pr-1 scrollbar-hide">
                    {displayedSnapshots.length === 0 ? (
                      <div className="text-xs text-white/55 py-3">No versions yet.</div>
                    ) : displayedSnapshots.map((snapshot) => {
                      const isCurrent = snapshot.version_index === snapshotCursor;
                      const isReverting = revertingSnapshot === snapshot.version_index;
                      return (
                        <button
                          key={snapshot.id || snapshot.version_index}
                          onClick={() => {
                            if (isCurrent || isReverting) return;
                            onRevertSnapshot?.(snapshot.version_index);
                          }}
                          disabled={isCurrent || isReverting || snapshotsLoading}
                          className={`w-full text-left px-3 py-3 rounded-xl border transition-all ${isCurrent
                            ? 'border-cyan/55 bg-cyan/15'
                            : 'border-white/10 bg-white/[0.03] hover:border-cyan/35 hover:bg-cyan/10'
                            } ${isReverting ? 'opacity-70' : ''}`}
                        >
                          <p className="text-xs text-white/80 leading-relaxed line-clamp-2">
                            {snapshot.description || 'Saved itinerary'}
                          </p>
                          <div className="mt-2 text-[10px] uppercase tracking-wider text-white/35">
                            {formatSnapshotDate(snapshot.created_at)}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      <div
        className={`flex-1 flex flex-col items-center px-3 sm:px-6 lg:px-10 py-4 sm:py-6 lg:py-8 relative w-full scrollbar-hide ${selectedDay == null ? 'overflow-y-auto' : 'overflow-hidden'
          } ${(!hasStarted || (errorType && !hasDayCards)) ? 'justify-center' : 'justify-start'}`}
      >
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
          /* Grid vs frame: replace day-cards grid with the centered frame when a day is selected. */
          <div className="w-full h-full flex-1 relative">
            <AnimatePresence mode="wait">
              {selectedDay == null ? (
                <motion.div
                  key="grid"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.22 } }}
                  transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
                  className="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-y-12 gap-x-12 pb-10 pt-4 max-w-5xl mx-auto"
                >
                  {itineraryState.days.map((day, index) => (
                    <div
                      key={day.dayNumber}
                      className={`relative flex flex-col h-full z-10 w-full ${(index === itineraryState.days.length - 1 && itineraryState.days.length % 2 !== 0) ||
                        itineraryState.days.length === 1
                        ? 'md:col-span-2 md:w-1/2 md:mx-auto'
                        : ''
                        }`}
                    >
                      <DayCard
                        day={day}
                        index={index}
                        destinations={itineraryState.journey}
                        onSelect={(n) => {
                          setNavDirection(1);
                          setSelectedDay(n);
                        }}
                      />
                    </div>
                  ))}
                </motion.div>
              ) : selectedDayData ? (
                <motion.div
                  key="overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, transition: { duration: 0.2 } }}
                  transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
                  className="absolute inset-0 flex items-stretch justify-center w-full h-full max-w-5xl mx-auto px-1 py-4"
                  onClick={(e) => {
                    if (e.target === e.currentTarget) handleCloseOverlay();
                  }}
                >
                  {/* Frame stays mounted across day navigation; only its body content animates. */}
                  <ExpandedFrame
                    day={selectedDayData}
                    allDays={itineraryState.days}
                    destinations={itineraryState.journey}
                    onClose={handleCloseOverlay}
                    onNavigate={handleNavigate}
                    bodyKey={viewMode}
                    actionButton={

                      viewMode === 'expanded' ? (
                        <button
                          onClick={() => handleOpenMap()}
                          className="flex items-center gap-1.5 px-3 py-2 text-cyan text-xs font-bold uppercase tracking-wider hover:scale-110 transition-all w-[6rem] justify-center"
                          title="View on map"
                        >
                          <MapIcon className="w-3.5 h-3.5" />
                          <span className="hidden sm:inline">Map</span>
                        </button>
                      ) : (
                        <button
                          onClick={handleBackToCard}
                          className="flex items-center gap-1.5 px-3 py-2 text-cyan text-xs font-bold uppercase tracking-wider hover:scale-110 transition-all w-[6rem] justify-center"
                          title="Back to card"
                        >
                          <Activity className="w-3.5 h-3.5" />
                          <span className="hidden sm:inline">Events</span>
                        </button>
                      )
                    }
                  >
                    {viewMode === 'expanded' ? (
                      <ExpandedDayCardBody
                        day={selectedDayData}
                        onViewOnMap={handleViewOnMap}
                        onToggleLock={onToggleLock}
                        navDirection={navDirection}
                      />
                    ) : (
                      <DayMapViewBody
                        day={selectedDayData}
                        allDays={itineraryState.days}
                        highlightedEventKey={highlightedEventKey}
                        onNavigateToDay={handleNavigateToDay}
                        isGenerating={isGenerating}
                      />
                    )}
                  </ExpandedFrame>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function formatSnapshotDate(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}
