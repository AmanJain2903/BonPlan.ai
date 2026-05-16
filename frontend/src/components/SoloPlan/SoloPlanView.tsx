import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { api, Plan, TripItinerary, SmartAnchor, ItinerarySnapshot } from '../../apis/plan';
import { Bot, Minimize2, ArrowLeftRight, MessageSquare, X as XIcon, Zap, Info } from 'lucide-react';

import { EASE_OUT_EXPO, replayEvents } from './constants';
import {
  ItineraryState,
  ChatTurn,
  ChatMode,
  PageState,
  GenerationSession,
  AttachedEventRef,
  ChatHistoryEntry,
} from './types';
import { generationManager } from './generationManager';
import FloatingRestoreButton from './FloatingRestoreButton';
import TripSummaryPills from './TripSummaryPills';
import ItineraryPanel from './ItineraryPanel';
import HeroPanel from './HeroPanel';
import MessageCanvas from './MessageCanvas';
import ChatInputBar from './ChatInputBar';
import TripShareMenu from './TripShareMenu';
import SmartAnchorsModal from './SmartAnchorsModal';
import {
  DeleteTripModal,
  OpenBookingsMenu,
  TripNavigationControls,
} from './TripHeaderControls';

function derivePageState(
  plan: Plan | null,
  tripItinerary: TripItinerary | null,
  generatingOverride: boolean,
): PageState {
  if (generatingOverride) return 'GENERATING';
  if (!plan || !tripItinerary) return 'DRAFT';

  const planStatus = (plan.status || '').toUpperCase();
  const itinStatus = (tripItinerary.status || '').toUpperCase();

  if (
    (planStatus === 'GENERATED' || planStatus === 'EDITING') &&
    itinStatus === 'GENERATED'
  ) {
    return 'EDITING';
  }

  return 'DRAFT';
}

export default function SoloPlanView() {
  const { tripId } = useParams<{ tripId: string }>();
  const navigate = useNavigate();
  const { isLoggedIn, user } = useAuth();

  const [plan, setPlan] = useState<Plan | null>(null);
  const [tripItinerary, setTripItinerary] = useState<TripItinerary | null>(null);
  const [loading, setLoading] = useState(true);

  const [chatMode, setChatMode] = useState<ChatMode>('autonomous');
  const [useFastModel, setUseFastModel] = useState<boolean>(() => {
  try {
    const storedValue = localStorage.getItem('bonplan_fast_mode');
    
    // If it doesn't exist yet, default to false
    if (storedValue === null) {
      return false;
    }
    
    // Otherwise, return true only if the stored string is 'true'
    return storedValue === 'true';
    
  } catch {
    // Fallback if localStorage is unavailable (e.g., SSR or blocked by browser)
    return false; 
  }
});
  const [showFastInfo, setShowFastInfo] = useState(false);
  const fastInfoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [contextMessage, setContextMessage] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<AttachedEventRef[]>([]);

  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [itineraryState, setItineraryState] = useState<ItineraryState>({ days: [] });
  const [errorType, setErrorType] = useState<'stopped' | 'error' | null>(null);
  const [generatingOverride, setGeneratingOverride] = useState(false);
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [isWaitingForUser, setIsWaitingForUser] = useState(false);

  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [generationStartedAt, setGenerationStartedAt] = useState<number | null>(null);

  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [thoughtsExpanded, setThoughtsExpanded] = useState(false);
  const [systemLogExpanded, setSystemLogExpanded] = useState(false);
  const [isChatMinimized, setIsChatMinimized] = useState(false);
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);
  const [isMobileScreen, setIsMobileScreen] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1024);
  const [deleteTripOpen, setDeleteTripOpen] = useState(false);
  const [deletingTrip, setDeletingTrip] = useState(false);
  const [deleteTripError, setDeleteTripError] = useState('');

  const [smartAnchors, setSmartAnchors] = useState<SmartAnchor[]>([]);
  const [anchorDrafts, setAnchorDrafts] = useState<SmartAnchor[]>([]);
  const [anchorsModalOpen, setAnchorsModalOpen] = useState(false);
  const [savingAnchors, setSavingAnchors] = useState(false);
  const [snapshots, setSnapshots] = useState<ItinerarySnapshot[]>([]);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [snapshotsError, setSnapshotsError] = useState('');
  const [revertingSnapshot, setRevertingSnapshot] = useState<number | null>(null);

  const messageEndRef = useRef<HTMLDivElement>(null);
  const thinkingEndRef = useRef<HTMLDivElement>(null);
  const summaryEndRef = useRef<HTMLDivElement>(null);
  const lastSnapshotRefreshCursorRef = useRef<number | null>(null);

  // Message Canvas Scroll Position and State
  const scrollPositionRef = useRef(0);
  const isAtBottomRef = useRef(true);

  const pageState = useMemo(
    () => derivePageState(plan, tripItinerary, generatingOverride),
    [plan, tripItinerary, generatingOverride],
  );

  const handleDeleteTrip = useCallback(async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !tripId) return;

    setDeletingTrip(true);
    setDeleteTripError('');
    try {
      const res = await api.deletePlan(token, tripId);
      if (res.status_code && res.status_code >= 400) {
        setDeleteTripError(res.message || 'Could not delete this trip.');
        return;
      }
      generationManager.clearSession(tripId);
      navigate('/');
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string; message?: string } } }).response?.data?.detail ||
            (err as { response?: { data?: { detail?: string; message?: string } } }).response?.data?.message
          : undefined;
      setDeleteTripError(detail || 'Could not delete this trip.');
    } finally {
      setDeletingTrip(false);
    }
  }, [navigate, tripId]);

  const handleSaveAnchors = useCallback(async (anchors: SmartAnchor[]) => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !tripId) return;
    setSavingAnchors(true);
    try {
      await api.updateSmartAnchors(token, tripId, anchors);
      setSmartAnchors(anchors);
      setAnchorDrafts([]);
      setAnchorsModalOpen(false);
    } finally {
      setSavingAnchors(false);
    }
  }, [tripId]);

  const handleToggleLock = useCallback(async (event: any) => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !tripId) return;
    const newLocked = !(event?.is_locked === true);
    try {
      await api.toggleEventLock(token, tripId, event.day_number, event.event_number, newLocked, event.event_id);
      setItineraryState((prev) => {
        const days = prev.days.map((day) => {
          if (day.dayNumber !== event.day_number) return day;
          const events = day.events.map((ev: any) =>
            (event.event_id ? ev.event_id === event.event_id : ev.event_number === event.event_number)
              ? { ...ev, is_locked: newLocked }
              : ev,
          );
          return { ...day, events };
        });
        return { ...prev, days };
      });
    } catch {
      // silently ignore
    }
  }, [tripId]);

  const refreshSnapshots = useCallback(async (showLoading = false) => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !tripId) return;
    if (showLoading) setSnapshotsLoading(true);
    setSnapshotsError('');
    try {
      const res = await api.getItinerarySnapshots(token, tripId);
      if (res.status_code && res.status_code >= 400) {
        setSnapshotsError(res.message || 'Could not load versions.');
        return;
      }
      setSnapshots(res.snapshots || []);
      if (typeof res.snapshot_cursor === 'number') {
        lastSnapshotRefreshCursorRef.current = res.snapshot_cursor;
        setItineraryState((prev) => ({ ...prev, snapshotCursor: res.snapshot_cursor }));
        setTripItinerary((prev) => prev ? { ...prev, snapshot_cursor: res.snapshot_cursor } : prev);
      }
    } catch {
      setSnapshotsError('Could not load versions.');
    } finally {
      if (showLoading) setSnapshotsLoading(false);
    }
  }, [tripId]);

  // Sync from generationManager subscription
  const handleSessionUpdate = useCallback((session: GenerationSession) => {
    setTurns([...session.turns]);
    setItineraryState({ ...session.itineraryState });
    setErrorType(session.errorType);
    setIsSessionActive(session.isActive);
    setIsWaitingForUser(!!session.isWaitingForUser);
    setGenerationStartedAt(session.startedAt ?? null);

    if (session.isActive) {
      // While the run is active, lock the displayed mode to whatever the
      // session was started in. Survives navigation away & back.
      setChatMode(session.mode);
      if (session.mode === 'editing') {
        setPlan((prev) => prev ? { ...prev, status: 'EDITING' } : prev);
      }
    }

    if (session.mode === 'editing' && (
      session.itineraryState.snapshotCursor !== undefined || session.itineraryState.eventsHash
    )) {
      setTripItinerary((prev) => prev ? {
        ...prev,
        events: flattenItineraryEvents(session.itineraryState),
        cost: session.itineraryState.tripCostEstimate ?? prev.cost,
        title: session.itineraryState.tripTitle ?? prev.title,
        tips: session.itineraryState.tripTips ?? prev.tips,
        status: 'GENERATED',
        snapshot_cursor: session.itineraryState.snapshotCursor ?? prev.snapshot_cursor,
        events_hash: session.itineraryState.eventsHash ?? prev.events_hash,
      } : prev);
    }

    if (!session.isActive && session.errorType == null) {
      setGeneratingOverride(false);
      setPlan((prev) => prev ? { ...prev, status: 'GENERATED' } : prev);
      setTripItinerary((prev) => prev ? { ...prev, status: 'GENERATED' } : prev);
      const cursor = session.itineraryState.snapshotCursor;
      if (
        session.mode === 'editing' &&
        typeof cursor === 'number' &&
        lastSnapshotRefreshCursorRef.current !== cursor
      ) {
        lastSnapshotRefreshCursorRef.current = cursor;
        void refreshSnapshots(false);
      }
      if (chatMode !== 'editing') setChatMode('editing');
    } else if (!session.isActive && session.errorType != null) {
      // Keep generatingOverride=true so the page stays on GENERATING
      // Don't reset plan/tripItinerary status; the UI handles error/stopped via errorType
    }
  }, [chatMode, refreshSnapshots]);

  const handleOpenSnapshots = useCallback(async () => {
    if (!tripId || snapshotsLoading) return;
    await refreshSnapshots(true);
  }, [tripId, snapshotsLoading, refreshSnapshots]);

  const handleRevertSnapshot = useCallback(async (versionIndex: number) => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !tripId || revertingSnapshot != null) return;
    setRevertingSnapshot(versionIndex);
    setSnapshotsError('');
    try {
      const res = await api.revertItinerary(token, tripId, versionIndex);
      if (res.status_code && res.status_code >= 400) {
        setSnapshotsError(res.message || 'Could not restore that version.');
        return;
      }
      setItineraryState((prev) => buildStateFromItineraryPayload(prev, tripItinerary, res));
      setTripItinerary((prev) => prev ? {
        ...prev,
        events: Array.isArray(res.events) ? res.events : prev.events,
        cost: res.cost ?? prev.cost,
        title: res.title ?? prev.title,
        tips: Array.isArray(res.tips) ? res.tips : prev.tips,
        status: 'GENERATED',
        snapshot_cursor: typeof res.snapshot_cursor === 'number' ? res.snapshot_cursor : prev.snapshot_cursor,
        events_hash: typeof res.events_hash === 'string' ? res.events_hash : prev.events_hash,
      } : prev);
      if (typeof res.snapshot_cursor === 'number') {
        lastSnapshotRefreshCursorRef.current = res.snapshot_cursor;
      }
      setPlan((prev) => prev ? { ...prev, status: 'GENERATED' } : prev);
      setSelectedEvents([]);
    } catch {
      setSnapshotsError('Could not restore that version.');
    } finally {
      setRevertingSnapshot(null);
    }
  }, [tripId, revertingSnapshot, tripItinerary]);

  // Subscribe to generationManager for this trip
  useEffect(() => {
    if (!tripId) return;
    const unsubscribe = generationManager.subscribe(tripId, handleSessionUpdate);
    return unsubscribe;
  }, [tripId, handleSessionUpdate]);

  const isTimerRunning = isSessionActive && !errorType;

  // Timer for active planner/editor run elapsed time.
  // Uses generationStartedAt (stored in the singleton GenerationManager session)
  // so elapsed survives navigation away and back without resetting to 0.
  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (isTimerRunning && generationStartedAt) {
      const tick = () => setElapsedSeconds(Math.floor((Date.now() - generationStartedAt) / 1000));
      tick();
      timerRef.current = setInterval(tick, 1000);
    } else if (!isTimerRunning) {
      setElapsedSeconds(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isTimerRunning, generationStartedAt]);

  // Mobile screen detection
  useEffect(() => {
    const check = () => setIsMobileScreen(window.innerWidth < 1024);
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Auth, RBAC, and initialization
  useEffect(() => {
    if (!isLoggedIn) {
      navigate('/');
      return;
    }

    const init = async () => {
      try {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        if (!token || !tripId) return;

        const rbacRes = await api.getRBAC(token, tripId);
        if (!rbacRes.rbac || !['owner', 'shared_editor', 'shared_viewer'].includes(rbacRes.rbac)) {
          navigate('/');
          return;
        }

        const planRes = await api.getPlan(token, tripId);
        if (!planRes.plan) {
          navigate('/');
          return;
        }

        setPlan(planRes.plan);
        const itin = planRes.tripItinerary || null;
        setTripItinerary(itin);
        lastSnapshotRefreshCursorRef.current =
          typeof itin?.snapshot_cursor === 'number' ? itin.snapshot_cursor : null;
        if (itin?.smart_anchors) setSmartAnchors(itin.smart_anchors);

        // Check if generationManager already has an active session (user navigated away and back)
        const existingSession = generationManager.getSession(tripId);
        if (existingSession) {
          setTurns([...existingSession.turns]);
          setItineraryState({ ...existingSession.itineraryState });
          setErrorType(existingSession.errorType);
          if (existingSession.isActive) {
            setGeneratingOverride(true);
            // Restore the chat-header label to whatever the session was
            // actually running in (collaborative vs autonomous), not the
            // local default that just got reset by the remount.
            setChatMode(existingSession.mode);
          }
        } else if (itin) {
          const replayed = replayEvents(itin);
          setItineraryState(replayed);

          // Detect interrupted partial generation (events exist but not fully generated, no active session)
          const hasEvents = itin.events && itin.events.length > 0;
          const itinStatus = (itin.status || '').toUpperCase();
          if (hasEvents && itinStatus !== 'GENERATED') {
            setErrorType('error');
          }
          else if (hasEvents && itinStatus === 'GENERATED') {
            setChatMode('editing');
            // If itin is GENERATED but plan status lags behind (DB inconsistency),
            // sync plan status locally so pageState resolves to EDITING, not DRAFT.
            // Without this, chatMode='editing' + pageState='DRAFT' causes startPlanner
            // to be reachable, which previously sent generation traffic to the chat endpoint.
            setPlan((prev) => {
              if (!prev) return prev;
              const s = (prev.status || '').toUpperCase();
              return s === 'GENERATED' || s === 'EDITING' ? prev : { ...prev, status: 'GENERATED' };
            });
          }
        }
      } catch (err) {
        navigate('/');
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [isLoggedIn, navigate, tripId]);

  // Start generation
  const startPlanner = useCallback(async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!plan || !token || !tripId) return;

    const inputText = contextMessage.trim();
    setGeneratingOverride(true);
    setErrorType(null);

    // Reset loading days that had errors back to loading
    setItineraryState((prev) => ({
      ...prev,
      days: prev.days.map((day) =>
        day.hasError ? { ...day, hasError: false, isLoading: true } : day
      ),
    }));

    const currentItineraryState = { ...itineraryState };
    // Reset error on days for the session
    currentItineraryState.days = currentItineraryState.days.map((day) =>
      day.hasError ? { ...day, hasError: false, isLoading: true } : day
    );

    generationManager.startGeneration(tripId, token, {
      chatInput: inputText,
      mode: chatMode === 'collaborative' ? 'collaborative' : 'autonomous',
      initialItineraryState: currentItineraryState,
      useFastModel,
    });
  }, [plan, tripId, contextMessage, chatMode, itineraryState, useFastModel]);

  const toggleMode = useCallback(() => {
    if (isSessionActive) return;
    setChatMode((prev) => (prev === 'collaborative' ? 'autonomous' : 'collaborative'));
  }, [isSessionActive]);

  const toggleFastModel = useCallback(() => {
    if (isSessionActive) return;
    setUseFastModel((prev) => {
      const next = !prev;
      try { localStorage.setItem('bonplan_fast_mode', String(next)); } catch { /* noop */ }
      return next;
    });
  }, [isSessionActive]);

  const stopPlanner = useCallback(() => {
    if (!tripId) return;
    generationManager.stopGeneration(tripId);
  }, [tripId]);

  const handleRetry = useCallback(() => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!tripId || !token) return;
    const session = generationManager.getSession(tripId);
    if (session?.lastRequest?.mode === 'editing') {
      generationManager.retryGeneration(tripId, token);
      return;
    }
    startPlanner();
  }, [startPlanner, tripId]);

  const handleAnswerQuestion = useCallback(
    async (params: { callId: string; answer: string | null; skipped: boolean }) => {
      const token = localStorage.getItem('token') || sessionStorage.getItem('token');
      if (!tripId || !token) return;
      await generationManager.answerQuestion(
        tripId,
        params.callId,
        params.answer,
        params.skipped,
        token,
      );
    },
    [tripId],
  );

  const handleMessageSend = useCallback(() => {
    const message = chatInput.trim();
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!message || !tripId || !token || !plan || chatMode !== 'editing') return;

    const chatHistory = buildChatHistory(turns);
    const cachedItineraryEvents = flattenItineraryEvents(itineraryState);
    const cachedTripInput = buildCachedTripInput(plan, user?.preferences, message);
    void generationManager.startGeneration(tripId, token, {
      chatInput: message,
      mode: 'editing',
      initialItineraryState: itineraryState,
      attachedEvents: [...selectedEvents],
      chatHistory,
      cachedItineraryEvents,
      cachedTripInput,
      cachedResearchFacts: {},
      baseSnapshotCursor: itineraryState.snapshotCursor ?? tripItinerary?.snapshot_cursor,
      baseEventsHash: itineraryState.eventsHash ?? tripItinerary?.events_hash,
      forceReloadItinerary: false,
      appendUserTurn: true,
      useFastModel,
    });
    setChatInput('');
    setSelectedEvents([]);
  }, [chatInput, tripId, plan, chatMode, turns, itineraryState, tripItinerary, user?.preferences, selectedEvents, useFastModel]);

  // Loading spinner
  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-10 flex items-center justify-center"
      >
        <div className="w-8 h-8 border-2 border-cyan/50 border-t-cyan rounded-full animate-spin" />
      </motion.div>
    );
  }

  if (!plan) return null;

  const isGenerating = pageState === 'GENERATING' || (pageState === 'EDITING' && isSessionActive);
  const canEdit = plan.role === 'owner' || plan.role === 'shared_editor';
  const isItineraryGenerated = (tripItinerary?.status || '').toLowerCase() === 'generated';
  const tripTitleForDelete = itineraryState.tripTitle || tripItinerary?.title || 'this trip';
  const leftControl = (
    <TripNavigationControls
      canDelete={plan.role === 'owner'}
      deleting={deletingTrip}
      deleteDisabled={isSessionActive}
      onBack={() => navigate('/')}
      onDelete={() => {
        setDeleteTripError('');
        setDeleteTripOpen(true);
      }}
    />
  );
  const shareControl = tripId && isItineraryGenerated && !isGenerating
    ? (
      <div className="flex items-center gap-2">
        <OpenBookingsMenu itineraryState={itineraryState} />
        <TripShareMenu tripId={tripId} plan={plan} />
      </div>
    )
    : undefined;
  const deleteModal = deleteTripOpen ? (
    <DeleteTripModal
      tripTitle={tripTitleForDelete}
      deleting={deletingTrip}
      error={deleteTripError}
      onCancel={() => {
        if (deletingTrip) return;
        setDeleteTripOpen(false);
        setDeleteTripError('');
      }}
      onConfirm={handleDeleteTrip}
    />
  ) : null;

  // Convert JSONB {year,month,day,timezoneId} to ISO date strings for the modal
  const anchorTripContext = (() => {
    const toIso = (d: any): string => {
      if (!d || !d.year || !d.month || !d.day) return '';
      return `${d.year}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`;
    };
    return {
      start_date: toIso(plan?.start_date),
      end_date: toIso(plan?.end_date),
      destinations: tripItinerary?.destinations ?? (plan?.destinations?.map((d: any) => typeof d === 'string' ? d : d?.name ?? '') ?? []),
      adults: plan?.adults ?? 1,
      children: plan?.children ?? 0,
      timezoneId: (plan?.start_date as any)?.timezoneId ?? '',
    };
  })();

  const anchorsModal = anchorsModalOpen ? (
    <SmartAnchorsModal
      savedAnchors={smartAnchors}
      drafts={anchorDrafts}
      setDrafts={setAnchorDrafts}
      saving={savingAnchors}
      tripContext={anchorTripContext}
      onSave={handleSaveAnchors}
      onClose={() => setAnchorsModalOpen(false)}
    />
  ) : null;

  // ─── DRAFT View ──────────────────────────────────────────────
  if (pageState === 'DRAFT') {
    if (!canEdit) {
      return (
        <>
          {deleteModal}
          {anchorsModal}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.3 } }}
            className="h-screen overflow-hidden bg-black flex flex-col pt-16"
          >
            <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-2 sm:p-4 lg:px-8 xl:px-12 pt-3 sm:pt-6 lg:pt-8 w-full max-h-[calc(100vh-64px)]">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan/5 via-carbon/20 to-black pointer-events-none" />
              <div className="w-full h-full max-w-[1400px] 2xl:max-w-[1600px] flex-1 flex flex-col items-center z-10 min-h-0 pb-2">
                <TripSummaryPills
                  plan={plan}
                  tripCostEstimate={tripItinerary?.cost ?? undefined}
                  actualCost={0}
                  isGenerating={false}
                  dynamicTitle={itineraryState.tripTitle}
                  dynamicJourney={itineraryState.journey}
                  leftControl={leftControl}
                />
                <div className="flex flex-1 items-center justify-center text-sm text-white/45">
                  This shared itinerary is not ready to view yet.
                </div>
              </div>
            </main>
          </motion.div>
        </>
      );
    }

    return (
      <>
        {deleteModal}
        {anchorsModal}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.3 } }}
          className="h-screen overflow-hidden bg-black flex flex-col pt-16"
        >
          <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-2 sm:p-4 lg:px-8 xl:px-12 pt-3 sm:pt-6 lg:pt-8 w-full max-h-[calc(100vh-64px)]">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan/5 via-carbon/20 to-black pointer-events-none" />

            <div className="w-full h-full max-w-[1400px] 2xl:max-w-[1600px] flex-1 flex flex-col items-center z-10 min-h-0 pb-2">
              <TripSummaryPills
                plan={plan}
                tripCostEstimate={itineraryState.tripCostEstimate ?? (tripItinerary?.cost ?? undefined)}
                actualCost={0}
                isGenerating={false}
                dynamicTitle={itineraryState.tripTitle}
                dynamicJourney={itineraryState.journey}
                leftControl={leftControl}
              />

            <motion.div
              layout
              initial={{ opacity: 0, scale: 0.9, clipPath: 'inset(10% 40% 10% 40% round 24px)', filter: 'blur(8px)' }}
              animate={{ opacity: 1, scale: 1, clipPath: 'inset(0% 0% 0% 0% round 24px)', filter: 'blur(0px)' }}
              transition={{ duration: 0.9, ease: EASE_OUT_EXPO }}
              className="w-full flex-1 flex min-h-0 gap-3 relative z-10 flex-col"
            >
              <motion.div
                layout
                className="flex flex-col bg-carbon/40 border border-white/[0.06] rounded-3xl overflow-hidden min-h-0"
                style={{ flex: 1 }}
              >
                <HeroPanel
                  plannerMode={chatMode === 'collaborative' ? 'collaborative' : 'autonomous'}
                  setPlannerMode={(mode) => setChatMode(mode)}
                  contextInput={contextMessage}
                  setContextInput={setContextMessage}
                  onStart={startPlanner}
                  hasEvents={itineraryState.hasStarted}
                  anchorCount={smartAnchors.length + anchorDrafts.filter(d => d.prefill_status === 'done').length}
                  onOpenAnchors={() => setAnchorsModalOpen(true)}
                  anchorPrefilling={anchorDrafts.some(d => d.prefill_status === 'loading')}
                />
              </motion.div>
            </motion.div>
            </div>
          </main>
        </motion.div>
      </>
    );
  }

  // ─── GENERATING / EDITING View ───────────────────────────────
  // ─── GENERATING / EDITING View ───────────────────────────────
  const modeLabel = pageState === 'EDITING'
    ? 'editing mode'
    : `${chatMode} mode`;

  return (
    <>
      {deleteModal}
      {anchorsModal}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.3 } }}
        className="h-screen overflow-hidden bg-black flex flex-col pt-16"
      >
        <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-2 sm:p-4 lg:px-8 xl:px-12 pt-3 sm:pt-6 lg:pt-8 w-full max-h-[calc(100vh-64px)]">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan/5 via-carbon/20 to-black pointer-events-none" />
          <FloatingRestoreButton visible={isChatMinimized} onRestore={() => setIsChatMinimized(false)} />

          <div className="w-full h-full max-w-[1400px] 2xl:max-w-[1600px] flex-1 flex flex-col items-center z-10 min-h-0 pb-2">
            <TripSummaryPills
              plan={plan}
              tripCostEstimate={itineraryState.tripCostEstimate ?? (tripItinerary?.cost ?? undefined)}
              actualCost={itineraryState.days.reduce((acc, day) => acc + day.cost, 0)}
              isGenerating={isGenerating}
              dynamicTitle={itineraryState.tripTitle}
              dynamicJourney={itineraryState.journey}
              leftControl={leftControl}
              shareControl={shareControl}
            />

          <motion.div
            initial={{ opacity: 0, scale: 0.9, clipPath: 'inset(10% 40% 10% 40% round 24px)', filter: 'blur(8px)' }}
            animate={{ opacity: 1, scale: 1, clipPath: 'inset(0% 0% 0% 0% round 24px)', filter: 'blur(0px)' }}
            transition={{ duration: 0.9, ease: EASE_OUT_EXPO }}
            className="w-full flex-1 flex min-h-0 gap-3 relative z-10 flex-row items-stretch"
          >
            {/* LEFT: Itinerary Panel */}
            <ItineraryPanel
              isChatMinimized={isChatMinimized || !canEdit || isMobileScreen}
              planStatus={pageState}
              itineraryState={itineraryState}
              errorType={errorType}
              onRetry={canEdit ? handleRetry : undefined}
              onToggleLock={handleToggleLock}
              snapshots={snapshots}
              snapshotCursor={itineraryState.snapshotCursor ?? tripItinerary?.snapshot_cursor}
              snapshotsLoading={snapshotsLoading}
              snapshotsError={snapshotsError}
              revertingSnapshot={revertingSnapshot}
              onOpenSnapshots={canEdit ? handleOpenSnapshots : undefined}
              onRevertSnapshot={canEdit && !isGenerating ? handleRevertSnapshot : undefined}
            />

            {/* RIGHT: Chat Panel — desktop only inline, mobile as overlay */}
            <AnimatePresence>
              {canEdit && !isChatMinimized && !isMobileScreen && (
                <motion.div
                  layout
                  initial={{ opacity: 0, width: 0, x: 20 }}
                  animate={{ opacity: 1, width: '30%', x: 0 }}
                  exit={{ opacity: 0, transition: { duration: 0.3 } }}
                  transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
                  className="flex flex-col bg-carbon/40 border border-white/[0.06] rounded-3xl overflow-hidden min-h-0"
                >
                  <motion.div
                    key="chat-content"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="flex-1 flex flex-col min-h-0"
                  >
                    {/* Chat Header */}
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4, delay: 0.3 }}
                      className="shrink-0 flex items-center gap-3 px-6 py-4 border-b border-white/[0.06]"
                    >
                      <Bot className="w-8 h-8 text-cyan shrink-0" />
                      <div className="flex flex-col">
                        <h3 className="text-sm font-bold text-white">BonPlan AI Planner</h3>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase tracking-widest text-cyan/70 font-semibold">
                            {modeLabel}
                          </span>
                          {!isSessionActive && pageState !== 'EDITING' && (
                            <button
                              onClick={toggleMode}
                              className="p-1 rounded-md text-cyan/40 hover:text-cyan hover:bg-cyan/10 transition-all"
                              title={`Switch to ${chatMode === 'autonomous' ? 'collaborative' : 'autonomous'} mode`}
                            >
                              <ArrowLeftRight className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>
                      {/* Fast mode toggle — desktop (hover tooltip) */}
                      <div className="ml-auto relative group flex items-center gap-1.5">
                        <button
                          onClick={toggleFastModel}
                          disabled={isSessionActive}
                          className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                            useFastModel
                              ? 'bg-cyan/15 text-cyan border border-cyan/40 shadow-[0_0_8px_rgba(102,252,241,0.25)]'
                              : 'bg-white/5 text-white/50 border border-white/20 hover:text-cyan/70 hover:border-cyan/30 hover:bg-cyan/5'
                          } ${isSessionActive ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                          title={useFastModel ? 'Fast mode on — click to disable' : 'Enable fast mode'}
                        >
                          <Zap className={`w-2.5 h-2.5 ${useFastModel ? 'animate-pulse' : ''}`} />
                          Fast
                        </button>
                        {/* Hover tooltip — positioned below the button inside the chat panel */}
                        <div className="pointer-events-none absolute top-full right-0 mt-2 w-48 rounded-xl bg-[#0d1117] border border-white/10 p-3 text-left opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50 shadow-2xl">
                          <p className="text-[13px] font-bold text-cyan mb-0.5">1.5x Faster</p>
                          <p className="text-[11px] text-white/70 mb-1.5">Speed Optimized Model</p>
                          <p className="text-[9px] text-white/35 leading-relaxed">Fast Mode is great for quick ideas. For deep, highly reliable planning, stick with Standard Mode.</p>
                        </div>
                      </div>
                      <button
                        onClick={() => setIsChatMinimized(true)}
                        className="p-2 rounded-xl text-white/40 hover:text-white hover:bg-white/5 transition-all"
                        title="Minimize Chat"
                      >
                        <Minimize2 className="w-4 h-4" />
                      </button>
                    </motion.div>

                    <MessageCanvas
                      scrollPositionRef={scrollPositionRef}
                      isAtBottomRef={isAtBottomRef}
                      turns={turns}
                      toolsExpanded={toolsExpanded}
                      onToggleTools={() => setToolsExpanded((p) => !p)}
                      thoughtsExpanded={thoughtsExpanded}
                      onToggleThoughts={() => setThoughtsExpanded((p) => !p)}
                      systemLogExpanded={systemLogExpanded}
                      onToggleSystemLog={() => setSystemLogExpanded((p) => !p)}
                      onRetry={handleRetry}
                      errorType={errorType}
                      messageEndRef={messageEndRef}
                      thinkingEndRef={thinkingEndRef}
                      summaryEndRef={summaryEndRef}
                      onAnswerQuestion={handleAnswerQuestion}
                      isWaitingForUser={isWaitingForUser}
                    />

                    <ChatInputBar
                      isGenerating={isGenerating}
                      chatMode={chatMode}
                      chatInput={chatInput}
                      setChatInput={setChatInput}
                      itineraryDays={itineraryState.days}
                      selectedEvents={selectedEvents}
                      setSelectedEvents={setSelectedEvents}
                      onSend={handleMessageSend}
                      onStop={stopPlanner}
                      elapsedSeconds={elapsedSeconds}
                      errorType={errorType}
                    />
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Mobile chat FAB */}
          {canEdit && isMobileScreen && (
            <button
              onClick={() => setIsMobileChatOpen(true)}
              className="fixed bottom-6 right-5 z-40 flex items-center gap-2 rounded-2xl border border-cyan/30 bg-midnight/90 backdrop-blur-md px-4 py-3 text-sm font-semibold text-cyan shadow-[0_0_20px_rgba(102,252,241,0.15)] hover:bg-cyan/10 transition-all"
            >
              <MessageSquare className="w-4 h-4" />
              {isGenerating ? 'Live' : 'Chat'}
              {isWaitingForUser && <span className="w-2 h-2 rounded-full bg-cyan animate-pulse ml-0.5" />}
            </button>
          )}

          {/* Mobile chat drawer */}
          <AnimatePresence>
            {canEdit && isMobileScreen && isMobileChatOpen && (
              <>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
                  onClick={() => setIsMobileChatOpen(false)}
                />
                <motion.div
                  initial={{ y: '100%' }}
                  animate={{ y: 0 }}
                  exit={{ y: '100%' }}
                  transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
                  className="fixed bottom-0 left-0 right-0 z-50 flex flex-col bg-[#0a0d12] border-t border-white/[0.08] rounded-t-3xl overflow-hidden"
                  style={{ height: '72vh' }}
                >
                  {/* Drawer handle */}
                  <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06] shrink-0">
                    <div className="flex items-center gap-3">
                      <Bot className="w-6 h-6 text-cyan shrink-0" />
                      <div className="flex flex-col">
                        <h3 className="text-sm font-bold text-white">BonPlan AI Planner</h3>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase tracking-widest text-cyan/70 font-semibold">
                            {modeLabel}
                          </span>
                          {!isSessionActive && pageState !== 'EDITING' && (
                            <button
                              onClick={toggleMode}
                              className="p-1 rounded-md text-cyan/40 hover:text-cyan hover:bg-cyan/10 transition-all"
                            >
                              <ArrowLeftRight className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                    {/* Fast mode toggle — mobile */}
                    <div className="flex items-center gap-1.5 ml-auto">
                      <button
                        onClick={toggleFastModel}
                        disabled={isSessionActive}
                        className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                          useFastModel
                            ? 'bg-cyan/15 text-cyan border border-cyan/40 shadow-[0_0_8px_rgba(102,252,241,0.25)]'
                            : 'bg-white/5 text-white/50 border border-white/20'
                        } ${isSessionActive ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                      >
                        <Zap className={`w-2.5 h-2.5 ${useFastModel ? 'animate-pulse' : ''}`} />
                        Fast
                      </button>
                      <button
                        onClick={() => {
                          if (fastInfoTimerRef.current) clearTimeout(fastInfoTimerRef.current);
                          setShowFastInfo(true);
                          fastInfoTimerRef.current = setTimeout(() => setShowFastInfo(false), 3000);
                        }}
                        className="p-1 rounded-md text-white/40 hover:text-white/70 transition-all"
                        title="About fast mode"
                      >
                        <Info className="w-3 h-3" />
                      </button>
                    </div>
                    <button
                      onClick={() => setIsMobileChatOpen(false)}
                      className="p-2 rounded-xl text-white/40 hover:text-white hover:bg-white/5 transition-all"
                    >
                      <XIcon className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Mobile fast-info modal — absolute within drawer so it respects overflow-hidden */}
                  <AnimatePresence>
                    {showFastInfo && (
                      <>
                        {/* Backdrop — closes on outside click */}
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.15 }}
                          className="absolute inset-0 z-[58]"
                          onClick={() => {
                            if (fastInfoTimerRef.current) clearTimeout(fastInfoTimerRef.current);
                            setShowFastInfo(false);
                          }}
                        />
                        {/* Card — positioned below the header, near the i button */}
                        <motion.div
                          initial={{ opacity: 0, scale: 0.95, y: -6 }}
                          animate={{ opacity: 1, scale: 1, y: 0 }}
                          exit={{ opacity: 0, scale: 0.95, y: -6 }}
                          transition={{ duration: 0.18 }}
                          className="absolute top-[56px] right-3 z-[59] w-52 rounded-2xl bg-[#0d1117] border border-white/10 p-4 shadow-2xl text-left"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <Zap className="w-4 h-4 text-cyan shrink-0" />
                            <p className="text-[15px] font-bold text-cyan">1.5x Faster</p>
                          </div>
                          <p className="text-[12px] text-white/70 mb-2">Speed Optimised Model</p>
                          <p className="text-[10px] text-white/35 leading-relaxed">Fast Mode is great for quick ideas. For deep, highly reliable planning, stick with Standard Mode.</p>
                        </motion.div>
                      </>
                    )}
                  </AnimatePresence>

                  <MessageCanvas
                    scrollPositionRef={scrollPositionRef}
                    isAtBottomRef={isAtBottomRef}
                    turns={turns}
                    toolsExpanded={toolsExpanded}
                    onToggleTools={() => setToolsExpanded((p) => !p)}
                    thoughtsExpanded={thoughtsExpanded}
                    onToggleThoughts={() => setThoughtsExpanded((p) => !p)}
                    systemLogExpanded={systemLogExpanded}
                    onToggleSystemLog={() => setSystemLogExpanded((p) => !p)}
                    onRetry={handleRetry}
                    errorType={errorType}
                    messageEndRef={messageEndRef}
                    thinkingEndRef={thinkingEndRef}
                    summaryEndRef={summaryEndRef}
                    onAnswerQuestion={handleAnswerQuestion}
                    isWaitingForUser={isWaitingForUser}
                  />

                  <ChatInputBar
                    isGenerating={isGenerating}
                    chatMode={chatMode}
                    chatInput={chatInput}
                    setChatInput={setChatInput}
                    itineraryDays={itineraryState.days}
                    selectedEvents={selectedEvents}
                    setSelectedEvents={setSelectedEvents}
                    onSend={handleMessageSend}
                    onStop={stopPlanner}
                    elapsedSeconds={elapsedSeconds}
                    errorType={errorType}
                  />
                </motion.div>
              </>
            )}
          </AnimatePresence>
          </div>
        </main>
      </motion.div>
    </>
  );
}

function flattenItineraryEvents(itineraryState: ItineraryState): any[] {
  return itineraryState.days
    .flatMap((day) => day.events || [])
    .map((event) => {
      if (!event || typeof event !== 'object') return event;
      const { _updatedAt, ...rest } = event;
      return rest;
    });
}

function buildCachedTripInput(plan: Plan, preferences: any, textualContext: string): Record<string, any> {
  const destinations = Array.isArray(plan.destinations) ? plan.destinations : [];
  return {
    hasMultipleDestinations: destinations.length > 1,
    planning_type: plan.planning_type,
    routing_style: plan.routing_style,
    origin: plan.origin,
    destinations,
    start_date: plan.start_date,
    end_date: plan.end_date,
    pace: plan.pace,
    budget: plan.budget,
    adults: plan.adults,
    children: plan.children,
    preferences: preferences || {},
    textualContext,
  };
}

function buildStateFromItineraryPayload(
  prev: ItineraryState,
  currentItinerary: TripItinerary | null,
  payload: {
    events?: any[];
    cost?: number | null;
    title?: string | null;
    tips?: string[];
    snapshot_cursor?: number;
    events_hash?: string;
  },
): ItineraryState {
  const events = Array.isArray(payload.events) ? payload.events : (currentItinerary?.events || []);
  const next = replayEvents({
    id: currentItinerary?.id || '',
    title: payload.title ?? currentItinerary?.title ?? prev.tripTitle ?? null,
    origin: currentItinerary?.origin ?? null,
    destinations: currentItinerary?.destinations?.length
      ? currentItinerary.destinations
      : (prev.journey || []),
    start_date: currentItinerary?.start_date ?? null,
    end_date: currentItinerary?.end_date ?? null,
    cost: payload.cost ?? currentItinerary?.cost ?? prev.tripCostEstimate ?? null,
    days: currentItinerary?.days ?? prev.days.length,
    events,
    tips: Array.isArray(payload.tips) ? payload.tips : (currentItinerary?.tips || prev.tripTips || []),
    status: 'GENERATED',
    smart_anchors: currentItinerary?.smart_anchors || [],
    snapshot_cursor: payload.snapshot_cursor,
    events_hash: payload.events_hash,
    created_at: currentItinerary?.created_at || '',
    updated_at: currentItinerary?.updated_at || '',
  });
  return {
    ...next,
    snapshotCursor: typeof payload.snapshot_cursor === 'number' ? payload.snapshot_cursor : prev.snapshotCursor,
    eventsHash: typeof payload.events_hash === 'string' ? payload.events_hash : prev.eventsHash,
  };
}

function buildChatHistory(turns: ChatTurn[]): ChatHistoryEntry[] {
  const history: ChatHistoryEntry[] = [];

  for (const turn of turns) {
    if (turn.type === 'user') {
      const text = turn.text?.trim();
      if (text) history.push({ role: 'user', content: text });
      continue;
    }

    if (turn.type === 'qa_pair') {
      const question = turn.question?.trim();
      const answer = turn.answer?.trim();
      if (question) history.push({ role: 'assistant', content: question });
      if (answer) history.push({ role: 'user', content: answer });
      continue;
    }

    if (turn.type === 'bot') {
      const summary = turn.finalSummary?.trim();
      if (summary) history.push({ role: 'assistant', content: summary });
    }
  }

  return history.slice(-24);
}
