import { PaginatedHistory, PaginatedSessions } from '../types';

export async function createSession(): Promise<{ session_id: string; session_dir: string }> {
  const res = await fetch('/sessions', { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function fetchSessions(page: number = 1, pageSize: number = 20): Promise<PaginatedSessions> {
  const res = await fetch(`/sessions?page=${page}&page_size=${pageSize}`);
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
  return res.json();
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  const res = await fetch(`/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`Failed to rename session ${sessionId}: ${res.status}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete session ${sessionId}: ${res.status}`);
}

export async function fetchSessionHistory(
  sessionId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<PaginatedHistory> {
  const res = await fetch(`/sessions/${sessionId}/history?page=${page}&page_size=${pageSize}`);
  if (!res.ok) throw new Error(`Failed to fetch history for ${sessionId}: ${res.status}`);
  return res.json();
}
