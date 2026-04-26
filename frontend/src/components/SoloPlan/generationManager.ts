import { api } from '../../apis/plan';
import { GenerationSession, ChatTurn, BotTurn, ItineraryState, ItineraryDay } from './types';

type Subscriber = (session: GenerationSession) => void;

function updateLastBotTurn(turns: ChatTurn[], updater: (turn: BotTurn) => BotTurn): ChatTurn[] {
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    if (turns[i].type === 'bot') {
      const next = [...turns];
      next[i] = updater(turns[i] as BotTurn);
      return next;
    }
  }
  return turns;
}

function getEventCost(data: any): number {
  switch (data.event_type) {
    case 'FLIGHT_TAKEOFF':
      return data.flight_takeoff_details?.cost || 0;
    case 'HOTEL_CHECKIN':
      return data.hotel_checkin_details?.cost || 0;
    case 'ACTIVITY':
    case 'DINING':
      return data.place_details?.cost || 0;
    case 'CAR_PICKUP':
      return data.car_pickup_details?.cost || 0;
    case 'COMMUTE':
      return data.commute_details?.transit_fare || 0;
    case 'OTHER':
      return data.other_details?.cost || 0;
    default:
      return 0;
  }
}

function isCountableEvent(eventType: string): boolean {
  return ['HOTEL_CHECKIN', 'ACTIVITY', 'DINING', 'OTHER'].includes(eventType);
}

function processEventIntoItinerary(prev: ItineraryState, data: any): ItineraryState {
  if (!data) return prev;

  switch (data.event_type) {
    case 'START': {
      const startDetails = data.start_details;
      if (!startDetails) return prev;
      const days: ItineraryDay[] = Array.from({ length: startDetails.number_of_days }).map((_, i) => ({
        dayNumber: i + 1,
        title: '',
        date: '',
        events: [],
        eventsCount: 0,
        cost: 0,
        isLoading: true,
        hasError: false,
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
    default: {
      const dayNum = data.day_number;
      if (typeof dayNum !== 'number' || dayNum <= 0) return prev;
      const newCost = getEventCost(data);
      const newCountable = isCountableEvent(data.event_type) ? 1 : 0;

      return {
        ...prev,
        days: prev.days.map((day) => {
          if (day.dayNumber < dayNum) {
            return { ...day, isLoading: false };
          }
          if (day.dayNumber !== dayNum) return day;

          // Upsert by (day_number, event_number) so regenerated events replace
          // the prior entry instead of duplicating. Backend already upserts on
          // the same key (see backend/app/agent/api/v1/endpoints/solo_planner.py).
          const existingIdx = day.events.findIndex(
            (e: any) => e.event_number === data.event_number,
          );

          const timestamp = Date.now();
          const targetData = { ...data, _updatedAt: timestamp };

          if (existingIdx === -1) {
            return {
              ...day,
              title: targetData.day_title || day.title,
              date: targetData.date || day.date,
              events: [...day.events, targetData],
              eventsCount: day.eventsCount + newCountable,
              cost: day.cost + newCost,
              lastUpdatedAt: timestamp,
            };
          }

          const prevEvent = day.events[existingIdx];
          const prevCost = getEventCost(prevEvent);
          const prevCountable = isCountableEvent(prevEvent.event_type) ? 1 : 0;
          const nextEvents = [...day.events];
          nextEvents[existingIdx] = targetData;
          return {
            ...day,
            title: targetData.day_title || day.title,
            date: targetData.date || day.date,
            events: nextEvents,
            eventsCount: day.eventsCount - prevCountable + newCountable,
            cost: day.cost - prevCost + newCost,
            lastUpdatedAt: timestamp,
          };
        }),
      };
    }
  }
}

function flushThinking(turn: BotTurn): Pick<BotTurn, 'thoughtHistory' | 'activeThinkingBubble'> {
  if (!turn.activeThinkingBubble.trim()) {
    return { thoughtHistory: turn.thoughtHistory, activeThinkingBubble: turn.activeThinkingBubble };
  }
  return {
    thoughtHistory: turn.thoughtHistory + (turn.thoughtHistory ? '\n\n---\n\n' : '') + turn.activeThinkingBubble.trim(),
    activeThinkingBubble: '',
  };
}

function handleSSEChunk(session: GenerationSession, chunk: any): void {
  switch (chunk.type) {
    case 'thinking':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        activeThinkingBubble: turn.activeThinkingBubble + (chunk.content || ''),
        activePruningChunk: null,
      }));
      break;

    case 'tool_call':
      session.turns = updateLastBotTurn(session.turns, (turn) => {
        const hasTool = turn.toolHistory.some((t) => t.call_id === chunk.call_id);
        return {
          ...turn,
          ...flushThinking(turn),
          activeToolIndicator: { name: chunk.tool_name, call_id: chunk.call_id },
          activePruningChunk: null,
          toolHistory: hasTool
            ? turn.toolHistory
            : [...turn.toolHistory, { call_id: chunk.call_id, name: chunk.tool_name, args: chunk.args }],
        };
      });
      break;

    case 'tool_response':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        ...flushThinking(turn),
        toolHistory: turn.toolHistory.map((t) =>
          t.call_id === chunk.call_id ? { ...t, response: chunk.response } : t
        ),
        activeToolIndicator:
          turn.activeToolIndicator && turn.activeToolIndicator.call_id === chunk.call_id
            ? null
            : turn.activeToolIndicator,
        activePruningChunk: null,
      }));
      break;

    case 'pruning':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        ...flushThinking(turn),
        activeToolIndicator: null,
        activePruningChunk: chunk,
      }));
      break;

    case 'event':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        ...flushThinking(turn),
        activePruningChunk: null,
      }));
      session.itineraryState = processEventIntoItinerary(session.itineraryState, chunk.data);
      break;

    case 'summary':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        ...flushThinking(turn),
        activeToolIndicator: null,
        activePruningChunk: null,
        finalSummary: turn.finalSummary + (chunk.content || ''),
        systemLog: null,
      }));
      break;

    case 'system':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        ...flushThinking(turn),
        activePruningChunk: null,
        systemLog: { type: 'system', content: chunk.content, error: chunk.error },
      }));
      break;

    case 'error':
      session.turns = updateLastBotTurn(session.turns, (turn) => ({
        ...turn,
        ...flushThinking(turn),
        activeToolIndicator: null,
        activePruningChunk: null,
        systemLog: { type: 'error', content: chunk.content },
        isStreaming: false,
      }));
      session.errorType = 'error';
      break;

    default:
      console.log('[UNKNOWN CHUNK]', chunk);
  }
}

class GenerationManager {
  private sessions: Map<string, GenerationSession> = new Map();
  private subscribers: Map<string, Set<Subscriber>> = new Map();

  getSession(tripId: string): GenerationSession | null {
    return this.sessions.get(tripId) || null;
  }

  subscribe(tripId: string, callback: Subscriber): () => void {
    if (!this.subscribers.has(tripId)) {
      this.subscribers.set(tripId, new Set());
    }
    this.subscribers.get(tripId)!.add(callback);

    const session = this.sessions.get(tripId);
    if (session) {
      callback(session);
    }

    return () => {
      const subs = this.subscribers.get(tripId);
      if (subs) {
        subs.delete(callback);
        if (subs.size === 0) this.subscribers.delete(tripId);
      }
    };
  }

  private notify(tripId: string): void {
    const session = this.sessions.get(tripId);
    const subs = this.subscribers.get(tripId);
    if (session && subs) {
      for (const cb of subs) {
        cb(session);
      }
    }
  }

  private markLoadingDaysAsError(session: GenerationSession): void {
    session.itineraryState = {
      ...session.itineraryState,
      days: session.itineraryState.days.map((day) =>
        day.isLoading ? { ...day, hasError: true, isLoading: false } : day
      ),
    };
  }

  async startGeneration(
    tripId: string,
    token: string,
    options: { chatInput: string; mode: string; initialItineraryState?: ItineraryState }
  ): Promise<void> {
    const existing = this.sessions.get(tripId);
    if (existing?.isActive && existing.abortController) {
      existing.abortController.abort();
    }

    const controller = new AbortController();
    const baseItineraryState = options.initialItineraryState || { days: [] };

    // Filter out trailing error bot turn from previous failed attempt
    const cleanedTurns = existing?.turns ? [...existing.turns] : [];
    if (cleanedTurns.length > 0) {
      const lastTurn = cleanedTurns[cleanedTurns.length - 1];
      if (lastTurn.type === 'bot' && (lastTurn as BotTurn).systemLog?.type === 'error') {
        cleanedTurns.pop();
      }
    }

    const session: GenerationSession = {
      tripId,
      turns: cleanedTurns,
      itineraryState: baseItineraryState,
      errorType: null,
      isActive: true,
      abortController: controller,
    };

    session.turns = [
      ...session.turns,
      {
        id: `${Date.now()}-user`,
        type: 'user' as const,
        text: options.chatInput,
      },
      {
        id: `${Date.now()}-bot`,
        type: 'bot' as const,
        toolHistory: [],
        activeToolIndicator: null,
        activePruningChunk: null,
        thoughtHistory: '',
        activeThinkingBubble: '',
        finalSummary: '',
        systemLog: null,
        isStreaming: true,
      },
    ];

    this.sessions.set(tripId, session);
    this.notify(tripId);

    try {
      const response = await api.generateSoloPlan(
        token,
        tripId,
        { chatInput: options.chatInput, mode: options.mode },
        controller.signal,
      );

      if (!response.ok || !response.body) {
        session.turns = updateLastBotTurn(session.turns, (turn) => ({
          ...turn,
          systemLog: { type: 'error', content: 'Failed to connect to planner.' },
          isStreaming: false,
        }));
        session.errorType = 'error';
        session.isActive = false;
        this.markLoadingDaysAsError(session);
        this.notify(tripId);
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
            handleSSEChunk(session, chunk);
            this.notify(tripId);

            if (chunk.type === 'error') {
              session.isActive = false;
              this.markLoadingDaysAsError(session);
              this.notify(tripId);
              return;
            }
          } catch (err) {
            console.error('Error parsing SSE chunk', err, part);
          }
        }
      }

      if (buffer.trim() && buffer.trim().startsWith('data: ')) {
        try {
          const chunk = JSON.parse(buffer.trim().replace('data: ', ''));
          handleSSEChunk(session, chunk);
        } catch (err) {
          console.error('Error parsing final buffered SSE chunk', err);
        }
      }

      session.turns = updateLastBotTurn(session.turns, (turn) => ({ ...turn, isStreaming: false }));
      session.isActive = false;
      this.notify(tripId);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted by user for trip', tripId);
      } else {
        console.error('Stream connection failed:', err);
        session.turns = updateLastBotTurn(session.turns, (turn) => ({
          ...turn,
          systemLog: { type: 'error', content: 'Stream connection failed.' },
          isStreaming: false,
        }));
        session.errorType = 'error';
        this.markLoadingDaysAsError(session);
      }
      session.isActive = false;
      this.notify(tripId);
    }
  }

  stopGeneration(tripId: string): void {
    const session = this.sessions.get(tripId);
    if (!session) return;

    if (session.abortController) {
      session.abortController.abort();
      session.abortController = null;
    }

    session.turns = updateLastBotTurn(session.turns, (turn) => ({
      ...turn,
      activeToolIndicator: null,
      activePruningChunk: null,
      activeThinkingBubble: '',
      systemLog: { type: 'error', content: 'You stopped the generation.', userStopped: true },
      isStreaming: false,
    }));

    session.errorType = 'stopped';
    session.isActive = false;
    this.markLoadingDaysAsError(session);
    this.notify(tripId);
  }

  clearSession(tripId: string): void {
    this.sessions.delete(tripId);
  }
}

export const generationManager = new GenerationManager();
