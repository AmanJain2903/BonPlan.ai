import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { api, Plan, TripItinerary } from '../../apis/plan';
import { Bot, Minimize2, ArrowLeftRight } from 'lucide-react';

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

  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [thoughtsExpanded, setThoughtsExpanded] = useState(false);
  const [systemLogExpanded, setSystemLogExpanded] = useState(false);
  const [isChatMinimized, setIsChatMinimized] = useState(false);
  const [deleteTripOpen, setDeleteTripOpen] = useState(false);
  const [deletingTrip, setDeletingTrip] = useState(false);
  const [deleteTripError, setDeleteTripError] = useState('');

  const messageEndRef = useRef<HTMLDivElement>(null);
  const thinkingEndRef = useRef<HTMLDivElement>(null);
  const summaryEndRef = useRef<HTMLDivElement>(null);

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

  // Sync from generationManager subscription
  const handleSessionUpdate = useCallback((session: GenerationSession) => {
    setTurns([...session.turns]);
    setItineraryState({ ...session.itineraryState });
    setErrorType(session.errorType);
    setIsSessionActive(session.isActive);
    setIsWaitingForUser(!!session.isWaitingForUser);

    if (session.isActive) {
      // While the run is active, lock the displayed mode to whatever the
      // session was started in. Survives navigation away & back.
      setChatMode(session.mode);
    }

    if (!session.isActive && session.errorType == null) {
      setGeneratingOverride(false);
      setPlan((prev) => prev ? { ...prev, status: 'GENERATED' } : prev);
      setTripItinerary((prev) => prev ? { ...prev, status: 'GENERATED' } : prev);
      if (chatMode !== 'editing') setChatMode('editing');
    } else if (!session.isActive && session.errorType != null) {
      // Keep generatingOverride=true so the page stays on GENERATING
      // Don't reset plan/tripItinerary status; the UI handles error/stopped via errorType
    }
  }, [chatMode]);

  // Subscribe to generationManager for this trip
  useEffect(() => {
    if (!tripId) return;
    const unsubscribe = generationManager.subscribe(tripId, handleSessionUpdate);
    return unsubscribe;
  }, [tripId, handleSessionUpdate]);

  const isTimerRunning = isSessionActive && !errorType;

  // Timer for active planner/editor run elapsed time
  useEffect(() => {
    if (isTimerRunning) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isTimerRunning]);

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
          }
        }
      } catch (err) {
        console.error('SoloPlanView access error:', err);
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
      mode: chatMode === 'editing' ? 'editing' : chatMode,
      initialItineraryState: currentItineraryState,
    });
  }, [plan, tripId, contextMessage, chatMode, itineraryState]);

  const toggleMode = useCallback(() => {
    if (isSessionActive) return;
    setChatMode((prev) => (prev === 'collaborative' ? 'autonomous' : 'collaborative'));
  }, [isSessionActive]);

  const stopPlanner = useCallback(() => {
    if (!tripId) return;
    generationManager.stopGeneration(tripId);
  }, [tripId]);

  const handleRetry = useCallback(() => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!tripId || !token) return;
    if (chatMode === 'editing') {
      generationManager.retryGeneration(tripId, token);
      return;
    }
    startPlanner();
  }, [chatMode, startPlanner, tripId]);

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
      forceReloadItinerary: false,
      appendUserTurn: true,
    });
    setChatInput('');
    setSelectedEvents([]);
  }, [chatInput, tripId, plan, chatMode, turns, itineraryState, user?.preferences, selectedEvents]);

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

  // ─── DRAFT View ──────────────────────────────────────────────
  if (pageState === 'DRAFT') {
    if (!canEdit) {
      return (
        <>
          {deleteModal}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.3 } }}
            className="h-screen overflow-hidden bg-black flex flex-col pt-16"
          >
            <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-4 sm:p-6 lg:px-8 xl:px-12 pt-6 sm:pt-8 w-full max-h-[calc(100vh-64px)]">
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
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.3 } }}
          className="h-screen overflow-hidden bg-black flex flex-col pt-16"
        >
          <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-4 sm:p-6 lg:px-8 xl:px-12 pt-6 sm:pt-8 w-full max-h-[calc(100vh-64px)]">
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
                  hasEvents={itineraryState.days.some(day => day.events && day.events.length > 0)}
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
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.3 } }}
        className="h-screen overflow-hidden bg-black flex flex-col pt-16"
      >
        <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-4 sm:p-6 lg:px-8 xl:px-12 pt-6 sm:pt-8 w-full max-h-[calc(100vh-64px)]">
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
              isChatMinimized={isChatMinimized || !canEdit}
              planStatus={pageState}
              itineraryState={itineraryState}
              errorType={errorType}
              onRetry={canEdit ? handleRetry : undefined}
            />

            {/* RIGHT: Chat Panel */}
            <AnimatePresence>
              {canEdit && !isChatMinimized && (
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
                      <button
                        onClick={() => setIsChatMinimized(true)}
                        className="ml-auto p-2 rounded-xl text-white/40 hover:text-white hover:bg-white/5 transition-all"
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
