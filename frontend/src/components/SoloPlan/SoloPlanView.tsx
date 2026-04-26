import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { api, Plan, TripItinerary } from '../../apis/plan';
import { Bot, Minimize2, ArrowLeftRight } from 'lucide-react';

import { EASE_OUT_EXPO, replayEvents } from './constants';
import { ItineraryState, ChatTurn, ChatMode, PageState, GenerationSession } from './types';
import { generationManager } from './generationManager';
import FloatingRestoreButton from './FloatingRestoreButton';
import TripSummaryPills from './TripSummaryPills';
import ItineraryPanel from './ItineraryPanel';
import HeroPanel from './HeroPanel';
import MessageCanvas from './MessageCanvas';
import ChatInputBar from './ChatInputBar';

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
  const { isLoggedIn } = useAuth();

  const [plan, setPlan] = useState<Plan | null>(null);
  const [tripItinerary, setTripItinerary] = useState<TripItinerary | null>(null);
  const [loading, setLoading] = useState(true);

  const [chatMode, setChatMode] = useState<ChatMode>('autonomous');
  const [contextMessage, setContextMessage] = useState('');
  const [chatInput, setChatInput] = useState('');

  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [itineraryState, setItineraryState] = useState<ItineraryState>({ days: [] });
  const [errorType, setErrorType] = useState<'stopped' | 'error' | null>(null);
  const [generatingOverride, setGeneratingOverride] = useState(false);
  const [isSessionActive, setIsSessionActive] = useState(false);

  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [thoughtsExpanded, setThoughtsExpanded] = useState(false);
  const [systemLogExpanded, setSystemLogExpanded] = useState(false);
  const [isChatMinimized, setIsChatMinimized] = useState(false);

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

  // Sync from generationManager subscription
  const handleSessionUpdate = useCallback((session: GenerationSession) => {
    setTurns([...session.turns]);
    setItineraryState({ ...session.itineraryState });
    setErrorType(session.errorType);
    setIsSessionActive(session.isActive);

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

  // Timer for generation elapsed time
  useEffect(() => {
    if (pageState === 'GENERATING' && !errorType) {
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
  }, [pageState, errorType]);

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
        if (!rbacRes.rbac || (rbacRes.rbac !== 'owner' && rbacRes.rbac !== 'shared_editor')) {
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
    startPlanner();
  }, [startPlanner]);

  const handleMessageSend = useCallback(() => {
    const message = chatInput.trim();
    if (!message) return;

    setTurns((prev) => [
      ...prev,
      { id: `${Date.now()}-user`, type: 'user', text: message },
      {
        id: `${Date.now()}-bot`,
        type: 'bot',
        toolHistory: [],
        activeToolIndicator: null,
        activePruningChunk: null,
        thoughtHistory: '',
        activeThinkingBubble: '',
        finalSummary: 'Message Received. Pending Development.',
        systemLog: null,
        isStreaming: false,
      },
    ]);
    setChatInput('');
  }, [chatInput]);

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

  const isGenerating = pageState === 'GENERATING';

  // ─── DRAFT View ──────────────────────────────────────────────
  if (pageState === 'DRAFT') {
    return (
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
    );
  }

  // ─── GENERATING / EDITING View ───────────────────────────────
  // ─── GENERATING / EDITING View ───────────────────────────────
  const modeLabel = pageState === 'EDITING'
    ? 'editing mode'
    : `${chatMode} mode`;

  return (
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
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.9, clipPath: 'inset(10% 40% 10% 40% round 24px)', filter: 'blur(8px)' }}
            animate={{ opacity: 1, scale: 1, clipPath: 'inset(0% 0% 0% 0% round 24px)', filter: 'blur(0px)' }}
            transition={{ duration: 0.9, ease: EASE_OUT_EXPO }}
            className="w-full flex-1 flex min-h-0 gap-3 relative z-10 flex-row items-stretch"
          >
            {/* LEFT: Itinerary Panel */}
            <ItineraryPanel
              isChatMinimized={isChatMinimized}
              planStatus={pageState}
              itineraryState={itineraryState}
              errorType={errorType}
              onRetry={handleRetry}
            />

            {/* RIGHT: Chat Panel */}
            <AnimatePresence>
              {!isChatMinimized && (
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
                    />

                    <ChatInputBar
                      isGenerating={isGenerating}
                      chatMode={chatMode}
                      chatInput={chatInput}
                      setChatInput={setChatInput}
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
  );
}
