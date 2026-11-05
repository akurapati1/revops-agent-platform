import type { Tokens } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const KEY = "revops.tokens";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

export function getTokens(): Tokens | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function setTokens(t: Tokens | null) {
  try {
    if (t) window.localStorage.setItem(KEY, JSON.stringify(t));
    else window.localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}

let refreshing: Promise<boolean> | null = null;

async function refresh(): Promise<boolean> {
  const t = getTokens();
  if (!t) return false;
  refreshing ??= fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: t.refresh_token }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      setTokens((await r.json()) as Tokens);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

interface Opts extends Omit<RequestInit, "body"> {
  json?: unknown;
  form?: FormData;
  auth?: boolean;
}

export async function api<T>(path: string, opts: Opts = {}, retry = true): Promise<T> {
  const { json, form, auth = true, headers, ...rest } = opts;
  const h = new Headers(headers);
  if (json !== undefined) h.set("Content-Type", "application/json");
  const tokens = getTokens();
  if (auth && tokens) h.set("Authorization", `Bearer ${tokens.access_token}`);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...rest, headers: h, body: form ?? (json !== undefined ? JSON.stringify(json) : undefined) });
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is the backend running?");
  }
  if (res.status === 401 && auth && retry && (await refresh())) return api<T>(path, opts, false);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const d = data as { detail?: string; code?: string } | null;
    throw new ApiError(res.status, typeof d?.detail === "string" ? d.detail : `Request failed (${res.status})`, d?.code);
  }
  return data as T;
}
