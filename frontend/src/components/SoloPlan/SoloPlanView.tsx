import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { api, Plan } from '../../apis/plan';
import { Bot, Minimize2 } from 'lucide-react';

import { EASE_OUT_EXPO } from './constants';
import { ToolEntry, SystemLog, ItineraryState, ItineraryDay } from './types';
import FloatingRestoreButton from './FloatingRestoreButton';
import TripSummaryPills from './TripSummaryPills';
import ItineraryPanel from './ItineraryPanel';
import HeroPanel from './HeroPanel';
import MessageCanvas from './MessageCanvas';
import ChatInputBar from './ChatInputBar';

// ─── Helpers ──────────────────────────────────────────────────

/** Flush active thinking text into the thought history string */
function flushThinking(
  setActiveThinking: React.Dispatch<React.SetStateAction<string>>,
  setThoughtHistory: React.Dispatch<React.SetStateAction<string>>,
) {
  setActiveThinking((prev) => {
    if (prev.trim()) {
      setThoughtHistory((hist) => hist + (hist ? '\n\n---\n\n' : '') + prev.trim());
    }
    return '';
  });
}

/** Process a single parsed SSE chunk and dispatch to the appropriate state setters */
function handleSSEChunk(
  chunk: any,
  setActiveThinking: React.Dispatch<React.SetStateAction<string>>,
  setThoughtHistory: React.Dispatch<React.SetStateAction<string>>,
  setActiveTool: React.Dispatch<React.SetStateAction<{ name: string; call_id: string } | null>>,
  setToolHistory: React.Dispatch<React.SetStateAction<ToolEntry[]>>,
  setFinalSummary: React.Dispatch<React.SetStateAction<string | null>>,
  setSystemLog: React.Dispatch<React.SetStateAction<SystemLog | null>>,
  setItineraryState: React.Dispatch<React.SetStateAction<ItineraryState>>,
) {
  switch (chunk.type) {
    case 'thinking':
      setActiveThinking((prev) => prev + (chunk.content || ''));
      break;

    case 'tool_call':
      flushThinking(setActiveThinking, setThoughtHistory);
      setActiveTool((prev) => {
        if (prev) {
          setToolHistory((hist) => {
            if (hist.some((t) => t.call_id === prev.call_id)) return hist;
            return [...hist, { call_id: prev.call_id, name: prev.name, args: null }];
          });
        }
        return { name: chunk.tool_name, call_id: chunk.call_id };
      });
      setToolHistory((prev) => {
        if (prev.find((t) => t.call_id === chunk.call_id)) return prev;
        return [...prev, { call_id: chunk.call_id, name: chunk.tool_name, args: chunk.args }];
      });
      break;

    case 'tool_response':
      setToolHistory((prev) =>
        prev.map((t) => (t.call_id === chunk.call_id ? { ...t, response: chunk.response } : t)),
      );
      setActiveTool((prev) => (prev && prev.call_id === chunk.call_id ? null : prev));
      break;

    case 'event':
      console.log('[EVENT]', chunk.data);
      setItineraryState((prev) => {
        const data = chunk.data;
        if (!data) return prev;

        switch (data.event_type) {
          case 'START': {
            const startDetails = data.start_details;
            if (!startDetails) return prev;

            const days: ItineraryDay[] = Array.from({ length: startDetails.number_of_days }).map((_, i) => ({
              dayNumber: i + 1,
              title: '',
              date: '',
              eventsCount: 0,
              cost: 0,
              isLoading: true,
            }));

            return {
              ...prev,
              hasStarted: true,
              tripTitle: startDetails.trip_title,
              tripCostEstimate: startDetails.trip_cost_estimate,
              journey: startDetails.journey,
              days,
            };
          }
          case 'FLIGHT_TAKEOFF': {
            const dayNum = data.day_number;
            const flightDetails = data.flight_takeoff_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    cost: day.cost + flightDetails.cost
                  };
                }
                return day;
              }),
            };
          }
          case 'FLIGHT_LAND': {
            const dayNum = data.day_number;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date
                  };
                }
                return day;
              }),
            };
          }
          case 'HOTEL_CHECKIN': {
            const dayNum = data.day_number;
            const hotelDetails = data.hotel_checkin_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    eventsCount: day.eventsCount + 1,
                    cost: day.cost + hotelDetails.cost
                  };
                }
                return day;
              }),
            };
          }
          case 'HOTEL_CHECKOUT': {
            const dayNum = data.day_number;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date
                  };
                }
                return day;
              }),
            };
          }
          case 'ACTIVITY': {
            const dayNum = data.day_number;
            const activityDetails = data.place_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    eventsCount: day.eventsCount + 1,
                    cost: day.cost + activityDetails.cost
                  };
                }
                return day;
              }),
            };
          }
          case 'DINING': {
            const dayNum = data.day_number;
            const diningDetails = data.place_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    eventsCount: day.eventsCount + 1,
                    cost: day.cost + diningDetails.cost
                  };
                }
                return day;
              }),
            };
          }
          case 'CAR_PICKUP': {
            const dayNum = data.day_number;
            const carDetails = data.car_pickup_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    cost: day.cost + carDetails.cost
                  };
                }
                return day;
              }),
            };
          }
          case 'CAR_DROPOFF': {
            const dayNum = data.day_number;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date
                  };
                }
                return day;
              }),
            };
          }
          case 'COMMUTE': {
            const dayNum = data.day_number;
            const commuteDetails = data.commute_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    cost: day.cost + (commuteDetails.transit_fare || 0)
                  };
                }
                return day;
              }),
            };
          }
          case 'OTHER': {
            const dayNum = data.day_number;
            const otherDetails = data.other_details;
            if (typeof dayNum !== 'number' || dayNum <= 0) return prev;

            return {
              ...prev,
              days: prev.days.map((day) => {
                if (day.dayNumber < dayNum) {
                  return { ...day, isLoading: false };
                }
                if (day.dayNumber === dayNum) {
                  return {
                    ...day,
                    title: data.day_title || day.title,
                    date: data.date || day.date,
                    eventsCount: day.eventsCount + 1,
                    cost: day.cost + otherDetails.cost
                  };
                }
                return day;
              }),
            };
          }
          case 'END': {
            const endDetails = data.end_details;
            if (!endDetails) return prev;
            return {
              ...prev,
              tripTitle: endDetails.trip_title,
              tripCostEstimate: endDetails.trip_cost,
              tripTips: endDetails.trip_tips,
              days: prev.days.map((day) => ({ ...day, isLoading: false })),
            };
          }
          default:
            return prev;
        }
      });
      break;

    case 'summary':
      flushThinking(setActiveThinking, setThoughtHistory);
      setFinalSummary(chunk.content);
      break;

    case 'system':
      setSystemLog({ type: 'system', content: chunk.content, error: chunk.error });
      break;

    case 'error':
      flushThinking(setActiveThinking, setThoughtHistory);
      setActiveTool(null);
      setSystemLog({ type: 'error', content: chunk.content });
      break;

    default:
      console.log('[UNKNOWN CHUNK]', chunk);
  }
}

// ─── Component ────────────────────────────────────────────────

export default function SoloPlanView() {
  const { tripId } = useParams<{ tripId: string }>();
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();

  // ── Plan data ──
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const [plannerMode, setPlannerMode] = useState<'autonomous' | 'collaborative'>('autonomous');
  const [chatInput, setChatInput] = useState('');

  // ── Itinerary state ──
  const [itineraryState, setItineraryState] = useState<ItineraryState>({ days: [] });

  // ── Error state for itinerary panel ──
  const [errorType, setErrorType] = useState<'stopped' | 'error' | null>(null);

  // ── Timer ──
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Tool tracking ──
  const [activeTool, setActiveTool] = useState<{ name: string; call_id: string } | null>(null);
  const [toolHistory, setToolHistory] = useState<ToolEntry[]>([]);
  const [toolsExpanded, setToolsExpanded] = useState(false);

  // ── Thinking tracking ──
  const [activeThinking, setActiveThinking] = useState('');
  const [thoughtHistory, setThoughtHistory] = useState('');
  const [thoughtsExpanded, setThoughtsExpanded] = useState(false);

  // ── Summary & logs ──
  const [finalSummary, setFinalSummary] = useState<string | null>(null);
  const [systemLog, setSystemLog] = useState<SystemLog | null>(null);
  const [systemLogExpanded, setSystemLogExpanded] = useState(false);
  const [isChatMinimized, setIsChatMinimized] = useState(false);

  // ── Refs ──
  const messageEndRef = useRef<HTMLDivElement>(null);
  const thinkingEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // ── Auto-scroll effects ──
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeTool, activeThinking, finalSummary, toolHistory, systemLog]);

  useEffect(() => {
    thinkingEndRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [activeThinking]);

  // ── Timer: start/stop based on plan.status ──
  useEffect(() => {
    if (plan?.status === 'generating') {
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
  }, [plan?.status]);

  // ─── SSE Stream Handler ─────────────────────────────────────

  const startPlanner = async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!plan || !token) return;

    // Reset all stream state
    setActiveTool(null);
    setToolHistory([]);
    setActiveThinking('');
    setThoughtHistory('');
    setFinalSummary(null);
    setSystemLog(null);
    setItineraryState({ days: [] });
    setErrorType(null);

    // Update local plan status to generating (backend does this too via the endpoint)
    setPlan((prev) => prev ? { ...prev, status: 'generating' } : prev);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Shared args for handleSSEChunk
    const chunkArgs = [
      setActiveThinking, setThoughtHistory, setActiveTool,
      setToolHistory, setFinalSummary, setSystemLog, setItineraryState,
    ] as const;

    try {
      const response = await api.generateSoloPlan(
        token,
        plan.id,
        { chatInput, mode: plannerMode },
        controller.signal,
      );

      if (!response.ok) {
        console.error('Failed to start planner', await response.text());
        setSystemLog({ type: 'error', content: 'Failed to connect to planner.' });
        setErrorType('error');
        setPlan((prev) => prev ? { ...prev, status: 'draft' } : prev);
        return;
      }

      if (!response.body) {
        console.error('No response body in stream');
        setErrorType('error');
        setPlan((prev) => prev ? { ...prev, status: 'draft' } : prev);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const chunk = JSON.parse(part.replace('data: ', ''));
            handleSSEChunk(chunk, ...chunkArgs);
            // If we got an error chunk from the backend, abort the stream
            if (chunk.type === 'error') {
              setErrorType('error');
              setActiveTool(null);
              setPlan((prev) => prev ? { ...prev, status: 'draft' } : prev);
              // Persist draft status to DB
              const t = localStorage.getItem('token') || sessionStorage.getItem('token');
              if (t && plan) {
                api.updatePlan(t, plan.id, {
                  startDate: plan.start_date,
                  endDate: plan.end_date,
                  pace: plan.pace,
                  budget: plan.budget,
                  adults: plan.adults,
                  children: plan.children,
                  status: 'draft',
                }).catch(console.error);
              }
              controller.abort();
              return;
            }
          } catch (err) {
            setSystemLog({ type: 'error', content: 'Error parsing SSE chunk' });
            console.error('Error parsing SSE chunk', err, part);
          }
        }
      }

      // Flush any remaining data left in the buffer after stream ends
      if (buffer.trim() && buffer.trim().startsWith('data: ')) {
        try {
          const chunk = JSON.parse(buffer.trim().replace('data: ', ''));
          handleSSEChunk(chunk, ...chunkArgs);
        } catch (err) {
          console.error('Error parsing final buffered SSE chunk', err, buffer);
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted by user');
        // stopPlanner already handles the state
      } else {
        console.error('Stream connection failed:', err);
        flushThinking(setActiveThinking, setThoughtHistory);
        setSystemLog({ type: 'error', content: 'Stream connection failed.' });
        setErrorType('error');
      }
    } finally {
      abortControllerRef.current = null;
      // On successful completion (not aborted), mark as generated
      setPlan((prev) => {
        if (!prev) return prev;
        // If user stopped, status was already set to 'draft' in stopPlanner
        // Only set to generated if still in generating state
        if (prev.status === 'generating') {
          // Persist to DB
          const t = localStorage.getItem('token') || sessionStorage.getItem('token');
          if (t) {
            api.updatePlan(t, prev.id, {
              startDate: prev.start_date,
              endDate: prev.end_date,
              pace: prev.pace,
              budget: prev.budget,
              adults: prev.adults,
              children: prev.children,
              status: 'generated',
            }).catch(console.error);
          }
          return { ...prev, status: 'generated' };
        }
        return prev;
      });
    }
  };

  const stopPlanner = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      flushThinking(setActiveThinking, setThoughtHistory);
      setActiveTool(null);
      setSystemLog({ type: 'error', content: 'You stopped the generation.', userStopped: true });
      setItineraryState({ days: [] });
      setErrorType('stopped');
    }
    // Revert plan status to draft (local + backend)
    setPlan((prev) => prev ? { ...prev, status: 'draft' } : prev);
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (token && plan) {
      try {
        await api.updatePlan(token, plan.id, {
          startDate: plan.start_date,
          endDate: plan.end_date,
          pace: plan.pace,
          budget: plan.budget,
          adults: plan.adults,
          children: plan.children,
          status: 'draft',
        });
      } catch (err) {
        console.error('Failed to revert plan status to draft:', err);
      }
    }
  };

  // ─── Auth & RBAC ────────────────────────────────────────────

  useEffect(() => {
    if (!isLoggedIn) {
      navigate('/');
      return;
    }
    const checkAccess = async () => {
      try {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        if (!token || !tripId) return;

        const rbacRes = await api.getRBAC(token, tripId);
        if (!rbacRes.rbac || (rbacRes.rbac !== 'owner' && rbacRes.rbac !== 'shared_editor')) {
          navigate('/');
          return;
        }

        const planRes = await api.getPlan(token, tripId);
        if (planRes.plan) {
          setPlan(planRes.plan);
        } else {
          navigate('/');
        }
      } catch (err) {
        console.error('SoloPlanView access error:', err);
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    checkAccess();
  }, [isLoggedIn, navigate, tripId]);

  // ─── Loading State ──────────────────────────────────────────

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

  // ─── Draft Plan View (only when status='draft' and no error overlay) ──

  if (plan.status === "draft" && !errorType) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.4, ease: EASE_OUT_EXPO } }}
        className="h-screen overflow-hidden bg-black flex flex-col pt-16"
      >
        <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-4 sm:p-6 lg:px-8 xl:px-12 pt-6 sm:pt-8 w-full max-h-[calc(100vh-64px)]">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan/5 via-carbon/20 to-black pointer-events-none" />

          <div className="w-full h-full max-w-[1400px] 2xl:max-w-[1600px] flex-1 flex flex-col items-center z-10 min-h-0 pb-2">
            <TripSummaryPills
              plan={plan}
              tripCostEstimate={itineraryState.tripCostEstimate}
              actualCost={itineraryState.days.reduce((acc, day) => acc + day.cost, 0)}
              planStatus={plan.status}
              dynamicTitle={itineraryState.tripTitle}
              dynamicJourney={itineraryState.journey}
            />

            {/* Main Content Area */}
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
                  plannerMode={plannerMode}
                  setPlannerMode={setPlannerMode}
                  chatInput={chatInput}
                  setChatInput={setChatInput}
                  onStart={startPlanner}
                />
              </motion.div>
            </motion.div>
          </div>
        </main>
      </motion.div>
    );
  }

  // ─── Generating / Generated / Editing / Completed / Error View ──────

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.4, ease: EASE_OUT_EXPO } }}
      className="h-screen overflow-hidden bg-black flex flex-col pt-16"
    >
      <main className="flex-1 min-h-0 flex flex-col items-center justify-start relative p-4 sm:p-6 lg:px-8 xl:px-12 pt-6 sm:pt-8 w-full max-h-[calc(100vh-64px)]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan/5 via-carbon/20 to-black pointer-events-none" />
        <FloatingRestoreButton visible={isChatMinimized} onRestore={() => setIsChatMinimized(false)} />

        <div className="w-full h-full max-w-[1400px] 2xl:max-w-[1600px] flex-1 flex flex-col items-center z-10 min-h-0 pb-2">
          <TripSummaryPills
            plan={plan}
            tripCostEstimate={itineraryState.tripCostEstimate}
            actualCost={itineraryState.days.reduce((acc, day) => acc + day.cost, 0)}
            planStatus={plan.status}
            dynamicTitle={itineraryState.tripTitle}
            dynamicJourney={itineraryState.journey}
          />

          {/* Main Content Area */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, clipPath: 'inset(10% 40% 10% 40% round 24px)', filter: 'blur(8px)' }}
            animate={{ opacity: 1, scale: 1, clipPath: 'inset(0% 0% 0% 0% round 24px)', filter: 'blur(0px)' }}
            transition={{ duration: 0.9, ease: EASE_OUT_EXPO }}
            className="w-full flex-1 flex min-h-0 gap-3 relative z-10 flex-row items-stretch"
          >
            {/* LEFT: Itinerary Panel */}
            <ItineraryPanel
              isChatMinimized={isChatMinimized}
              plannerMode={plannerMode}
              planStatus={plan.status}
              itineraryState={itineraryState}
              errorType={errorType}
            />

            {/* RIGHT: Chat Panel */}
            <AnimatePresence>
              {!isChatMinimized && (
                <motion.div
                  layout
                  initial={{ opacity: 0, width: 0, x: 20 }}
                  animate={{ opacity: 1, width: '30%', x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
                  className="flex flex-col bg-carbon/40 border border-white/[0.06] rounded-3xl overflow-hidden min-h-0"
                >
                  <motion.div
                    key="generating"
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
                        <span className="text-[10px] uppercase tracking-widest text-cyan/70 font-semibold">
                          {plan.status === 'generating'
                            ? `${plannerMode} mode`
                            : plan.status === 'generated' || plan.status === 'editing'
                              ? 'editing mode'
                              : `${plannerMode} mode`
                          }
                        </span>
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
                      chatInput={chatInput}
                      toolHistory={toolHistory}
                      toolsExpanded={toolsExpanded}
                      onToggleTools={() => setToolsExpanded((p) => !p)}
                      thoughtHistory={thoughtHistory}
                      thoughtsExpanded={thoughtsExpanded}
                      onToggleThoughts={() => setThoughtsExpanded((p) => !p)}
                      activeThinking={activeThinking}
                      isStreamComplete={plan.status !== 'generating'}
                      finalSummary={finalSummary}
                      activeTool={activeTool}
                      systemLog={systemLog}
                      systemLogExpanded={systemLogExpanded}
                      onToggleSystemLog={() => setSystemLogExpanded((p) => !p)}
                      onRetry={startPlanner}
                      messageEndRef={messageEndRef}
                      thinkingEndRef={thinkingEndRef}
                    />

                    <ChatInputBar
                      planStatus={plan.status}
                      plannerMode={plannerMode}
                      chatInput={chatInput}
                      setChatInput={setChatInput}
                      onStop={stopPlanner}
                      elapsedSeconds={elapsedSeconds}
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
