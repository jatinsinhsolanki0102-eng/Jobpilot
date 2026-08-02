"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, clearToken, getToken, setToken } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback((): Promise<void> => {
    const token = getToken();
    if (!token) {
      return Promise.resolve().then(() => {
        setUser(null);
        setLoading(false);
      });
    }
    return api
      .get<User>("/api/v1/auth/me")
      .then((me) => setUser(me))
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string }>("/api/v1/auth/login", {
      email,
      password,
    });
    setToken(res.access_token);
    const me = await api.get<User>("/api/v1/auth/me");
    setUser(me);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      const res = await api.post<{ access_token: string }>(
        "/api/v1/auth/register",
        { email, password, full_name: fullName }
      );
      setToken(res.access_token);
      const me = await api.get<User>("/api/v1/auth/me");
      setUser(me);
    },
    []
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
