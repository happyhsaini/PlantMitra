"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, clearSession, getToken, readCachedUser, setSession, type User } from "@/lib/api";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  setUser: (user: User | null) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const cached = readCachedUser();
    if (cached) setUser(cached);
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((fresh) => {
        setUser(fresh);
        const token = localStorage.getItem("plantmitra_token");
        if (token) setSession(token, fresh);
      })
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      setUser,
      logout: () => {
        clearSession();
        setUser(null);
        router.push("/login");
      },
    }),
    [user, loading, router],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
