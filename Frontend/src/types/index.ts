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

export interface TurnSegment {
  id: string;
  steps: AgentStep[];
  stepsCollapsed: boolean;
  text: string;
}

export interface ConversationTurn {
  id: string;
  userMessage: string;
  userFiles: string[];
  segments: TurnSegment[];
  isStreaming: boolean;
  streamPhase: 'idle' | 'steps' | 'text' | 'done';
  messageId?: string;                              // backend message_id for feedback
  feedbackSentiment?: 'liked' | 'disliked';       // set after feedback submitted
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

// Messages API types (replaces old history)
export interface MessageTurn {
  message_id: string;
  conversation_id: string;
  user_message: string;
  agent_response: string | null;
  error: string | null;
  files_uploaded: string[];
  is_liked: boolean | null;
  turns_used: number | null;
  cost_usd: number | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// SSE event types
// ---------------------------------------------------------------------------

export type AgentEventType =
  | 'session_start'
  | 'message_created'
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
  message_id?: string;
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
