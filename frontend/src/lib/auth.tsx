import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { api, json, refreshSession, session, type TokenResponse, type User } from '@/api/client';

type Status = 'loading' | 'authenticated' | 'anonymous';

interface AuthValue {
  status: Status;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

/**
 * A non-secret hint that this browser has signed in before. It only decides whether to probe
 * /auth/refresh on load (avoiding a pointless 401 for first-time visitors). The real session
 * is the httpOnly cookie, which JavaScript can never read.
 */
const HINT_KEY = 'akshara.session-hint';
const hint = {
  get: () => {
    try {
      return localStorage.getItem(HINT_KEY) === '1';
    } catch {
      return true;
    }
  },
  set: (on: boolean) => {
    try {
      if (on) localStorage.setItem(HINT_KEY, '1');
      else localStorage.removeItem(HINT_KEY);
    } catch {
      /* storage unavailable: fall back to always probing */
    }
  },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(() => (hint.get() ? 'loading' : 'anonymous'));
  const [user, setUser] = useState<User | null>(null);
  const queryClient = useQueryClient();

  const loadMe = useCallback(async () => {
    const me = await api<User>('/auth/me');
    setUser(me);
    setStatus('authenticated');
    hint.set(true);
  }, []);

  const drop = useCallback(() => {
    session.set(null);
    hint.set(false);
    setUser(null);
    setStatus('anonymous');
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    session.onLost(drop);
    // Restore the session from the httpOnly refresh cookie, if there is one.
    if (!hint.get()) return; // first visit: nothing to restore
    refreshSession()
      .then((ok) => (ok ? loadMe() : drop()))
      .catch(drop);
  }, [drop, loadMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api<TokenResponse>('/auth/login', { method: 'POST', ...json({ email, password }) });
      session.set(tokens.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      await api<User>('/auth/register', {
        method: 'POST',
        ...json({ email, password, display_name: displayName || null }),
      });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await api<void>('/auth/logout', { method: 'POST' });
    } finally {
      drop();
    }
  }, [drop]);

  const value = useMemo(
    () => ({ status, user, login, register, logout, setUser }),
    [status, user, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
