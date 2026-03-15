import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthUser {
  user_id: string;
  email: string;
  username: string;
  created_at: string;
}

interface AuthStore {
  user: AuthUser | null;
  token: string | null;
  setAuth: (user: AuthUser, token: string) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,

      setAuth: (user, token) => set({ user, token }),

      clearAuth: () => set({ user: null, token: null }),

      isAuthenticated: () => !!get().token && !!get().user,
    }),
    {
      name: 'claude-agent-auth',
    }
  )
);
