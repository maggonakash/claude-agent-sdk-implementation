import { PaginatedSessions } from '../types';
import { apiFetch } from './auth';

// Messages now come from /sessions/{id}/messages (not /history)
export interface PaginatedMessages {
  messages: MessageTurn[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

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

export async function createSession(): Promise<{ session_id: string; session_dir: string }> {
  const res = await apiFetch('/sessions', { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function fetchSessions(page: number = 1, pageSize: number = 20): Promise<PaginatedSessions> {
  const res = await apiFetch(`/sessions?page=${page}&page_size=${pageSize}`);
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
  return res.json();
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  const res = await apiFetch(`/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`Failed to rename session ${sessionId}: ${res.status}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete session ${sessionId}: ${res.status}`);
}

export async function fetchSessionMessages(
  sessionId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<PaginatedMessages> {
  const res = await apiFetch(
    `/sessions/${sessionId}/messages?page=${page}&page_size=${pageSize}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch messages for ${sessionId}: ${res.status}`);
  return res.json();
}
