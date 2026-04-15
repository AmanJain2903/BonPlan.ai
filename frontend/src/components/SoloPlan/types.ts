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
  eventsCount: number;
  cost: number;
  isLoading: boolean;
}

export interface ItineraryState {
  tripTitle?: string;
  tripCostEstimate?: number;
  journey?: string[];
  days: ItineraryDay[];
  hasStarted?: boolean;
  tripTips?: string[];
}
