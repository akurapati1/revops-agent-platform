"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getTokens, setTokens } from "./api";
import type { Me, Tokens } from "./types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (p: { email: string; password: string; name: string; org_name: string; invite_token?: string }) => Promise<void>;
  acceptTokens: (t: Tokens) => Promise<void>;
  switchOrg: (orgId: string) => Promise<void>;
  logout: () => void;
  reload: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const reload = useCallback(async () => {
    if (!getTokens()) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setTokens(null);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const acceptTokens = useCallback(async (t: Tokens) => {
    setTokens(t);
    await reload();
  }, [reload]);

  const value = useMemo<AuthState>(() => ({
    me, loading, reload, acceptTokens,
    login: async (email, password) => acceptTokens(await api<Tokens>("/auth/login", { method: "POST", json: { email, password }, auth: false })),
    signup: async (p) => acceptTokens(await api<Tokens>("/auth/signup", { method: "POST", json: p, auth: false })),
    switchOrg: async (orgId) => acceptTokens(await api<Tokens>("/auth/switch-org", { method: "POST", json: { org_id: orgId } })),
    logout: () => {
      setTokens(null);
      setMe(null);
      router.push("/login");
    },
  }), [me, loading, reload, acceptTokens, router]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
