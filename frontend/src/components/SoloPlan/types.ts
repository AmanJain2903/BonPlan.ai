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
}

export interface ItineraryState {
  tripTitle?: string;
  tripCostEstimate?: number;
  journey?: string[];
  days: ItineraryDay[];
  hasStarted?: boolean;
  tripTips?: string[];
}

export interface UserTurn {
  id: string;
  type: 'user';
  text: string;
}

export interface BotTurn {
  id: string;
  type: 'bot';
  toolHistory: ToolEntry[];
  activeToolIndicator: { name: string; call_id: string } | null;
  thoughtHistory: string;
  activeThinkingBubble: string;
  finalSummary: string;
  systemLog: SystemLog | null;
  isStreaming: boolean;
}

export type ChatTurn = UserTurn | BotTurn;

export type ChatMode = 'autonomous' | 'collaborative' | 'editing';

export type PageState = 'DRAFT' | 'GENERATING' | 'EDITING';

export interface GenerationSession {
  tripId: string;
  turns: ChatTurn[];
  itineraryState: ItineraryState;
  errorType: 'stopped' | 'error' | null;
  isActive: boolean;
  abortController: AbortController | null;
}
