export interface AgentStep {
  id: string;
  type: 'status' | 'tool' | 'error';
  text: string;
  tool?: string;
  summary?: string;
  completed: boolean;
  turn?: number;
  maxTurns?: number;
}

export interface ConversationTurn {
  id: string;
  userMessage: string;
  userFiles: string[];
  steps: AgentStep[];
  stepsCollapsed: boolean;
  agentText: string;
  isStreaming: boolean;
  streamPhase: 'idle' | 'steps' | 'text' | 'done';
  result?: {
    status: 'success' | 'error';
    text: string;
    turnsUsed?: number;
    costUsd?: number;
  };
  filesCreated: string[];
  error?: string;
  currentTurn?: number;
  maxTurns?: number;
  timestamp: Date;
  /** true = loaded from history (simplified display), false = live/streamed */
  fromHistory?: boolean;
}

export interface Chat {
  id: string;
  sessionId: string | null;
  title: string;
  turns: ConversationTurn[];
  createdAt: string;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

export interface SessionListItem {
  session_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedSessions {
  sessions: SessionListItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface HistoryEntry {
  role: string;
  content: string;
  timestamp: string;
}

export interface PaginatedHistory {
  history: HistoryEntry[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ---------------------------------------------------------------------------
// SSE event types
// ---------------------------------------------------------------------------

export type AgentEventType =
  | 'session_start'
  | 'status'
  | 'tool_start'
  | 'tool_end'
  | 'text_delta'
  | 'error'
  | 'result'
  | 'files'
  | 'done';

export interface AgentEvent {
  type: AgentEventType;
  session_id?: string;
  message?: string;
  tool?: string;
  summary?: string;
  text?: string;
  status?: string;
  result?: string;
  turns_used?: number;
  cost_usd?: number;
  files_modified?: string[];
  turn?: number;
  max_turns?: number;
}
