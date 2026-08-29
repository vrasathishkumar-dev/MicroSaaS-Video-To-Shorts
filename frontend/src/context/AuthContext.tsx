import { createContext, useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { getAccessToken } from '@/services/api';
import * as authService from '@/services/authService';
import type { User } from '@/types';

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Hydrates and holds the authenticated user for the whole app. On
 * mount, if an access token already exists in storage, fetches the
 * current user (GET /auth/me) so a refreshed page doesn't bounce back
 * to /login while a valid session is still live.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const me = await authService.getMe();
    setUser(me);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      if (!getAccessToken()) {
        setIsLoading(false);
        return;
      }
      try {
        const me = await authService.getMe();
        if (!cancelled) {
          setUser(me);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      await authService.login(email, password);
      await refreshUser();
    },
    [refreshUser],
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await authService.register(email, password, fullName);
      await authService.login(email, password);
      await refreshUser();
    },
    [refreshUser],
  );

  const logout = useCallback(async () => {
    await authService.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
