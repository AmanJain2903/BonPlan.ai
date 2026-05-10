export interface ToolEntry {
  call_id: string;
  name: string;
  args: any;
  response?: any;
}

export interface SystemLog {
  type: 'system' | 'error';
  content: string;
  error?: string;
  userStopped?: boolean;
}

export interface ItineraryDay {
  dayNumber: number;
  title: string;
  date: string;
  events: any[];
  eventsCount: number;
  cost: number;
  isLoading: boolean;
  hasError: boolean;
  lastUpdatedAt?: number;
}

export interface ItineraryState {
  tripTitle?: string;
  tripCostEstimate?: number;
  journey?: string[];
  days: ItineraryDay[];
  hasStarted?: boolean;
  tripTips?: string[];
  snapshotCursor?: number;
  eventsHash?: string;
}

export interface UserTurn {
  id: string;
  type: 'user';
  text: string;
  attachedEvents?: AttachedEventRef[];
}

export interface PendingQuestion {
  callId: string;
  question: string;
  options: string[];
  answerType: 'single' | 'multiple';
  skippable: boolean;
  // Local UI state — not on the wire.
  selectedOptions: string[];
  customAnswer: string;
  // When the user types free text we hide chip selections; when they
  // re-activate a chip we hide free text but keep it stashed so it
  // restores if every chip is later deselected.
  stashedFreeText: string;
  status: 'pending' | 'answered' | 'skipped' | 'stale';
}

/**
 * A frozen Q&A exchange that gets inserted into the chat history once the
 * user answers a pending question. Rendered as a single composite block so
 * the question always sits ABOVE the answer in display, regardless of the
 * surrounding newest-first ordering.
 */
export interface QAPairTurn {
  id: string;
  type: 'qa_pair';
  question: string;
  answer: string;
  skipped: boolean;
  staleInOtherTab?: boolean;
}

export interface BotTurn {
  id: string;
  type: 'bot';
  activeToolIndicator: { name: string; call_id: string } | null;
  activePruningChunk: any | null;
  thoughtHistory: string;
  activeThinkingBubble: string;
  finalSummary: string;
  systemLog: SystemLog | null;
  isStreaming: boolean;
  pendingQuestion: PendingQuestion | null;
}

export type ChatTurn = UserTurn | BotTurn | QAPairTurn;

export type ChatMode = 'autonomous' | 'collaborative' | 'editing';

export type PageState = 'DRAFT' | 'GENERATING' | 'EDITING';

export interface GenerationSession {
  tripId: string;
  // The mode the run was STARTED in. Persisted on the session so the chat
  // header label survives navigation (the local SoloPlanView state can flip
  // to 'editing' or be re-initialised on remount; this is the source of
  // truth for "what was running").
  mode: ChatMode;
  turns: ChatTurn[];
  itineraryState: ItineraryState;
  errorType: 'stopped' | 'error' | null;
  isActive: boolean;
  isWaitingForUser: boolean;
  abortController: AbortController | null;
  lastRequest: GenerationStartOptions | null;
  // Unix ms when the current active run started. Survives navigation so the
  // elapsed timer in SoloPlanView is computed from this rather than local
  // component state (which resets to 0 on remount).
  startedAt: number | null;
}

export interface AttachedEventRef {
  day_number: number;
  event_number: number;
  event_id?: string;
}

export interface ChatHistoryEntry {
  role: 'user' | 'assistant';
  content: string;
}

export interface GenerationStartOptions {
  chatInput: string;
  mode: string;
  initialItineraryState?: ItineraryState;
  attachedEvents?: AttachedEventRef[];
  chatHistory?: ChatHistoryEntry[];
  cachedItineraryEvents?: any[];
  cachedTripInput?: Record<string, any>;
  cachedResearchFacts?: Record<string, any>;
  baseSnapshotCursor?: number;
  baseEventsHash?: string;
  forceReloadItinerary?: boolean;
  appendUserTurn?: boolean;
  useFastModel?: boolean;
}
