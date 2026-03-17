import { useAuthStore } from '../store/authStore';

/** Thrown when the server returns 403 — caller should redirect to home or show access-denied UI. */
export class ForbiddenError extends Error {
  constructor() { super('Access denied'); this.name = 'ForbiddenError'; }
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    user_id: string;
    email: string;
    username: string;
    created_at: string;
  };
}

/**
 * Global fetch wrapper — attaches the JWT and handles 401 globally.
 * Any 401 response clears the stored token and redirects to /login,
 * preventing infinite retry loops when the token is missing or expired.
 */
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const token = useAuthStore.getState().token;
  const res = await fetch(url, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (res.status === 401) {
    useAuthStore.getState().clearAuth();
    window.location.replace('/login');
    throw new Error('Session expired. Redirecting to login…');
  }

  if (res.status === 403) {
    throw new ForbiddenError();
  }

  return res;
}

export async function loginApi(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(err.detail ?? 'Login failed');
  }
  return res.json();
}

export async function getMeApi() {
  const res = await apiFetch('/auth/me');
  if (!res.ok) throw new Error('Unauthorized');
  return res.json();
}

/** Attach the current JWT to any fetch options (kept for backward compat). */
export function withAuth(init: RequestInit = {}): RequestInit {
  const token = useAuthStore.getState().token;
  return {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
  };
}
