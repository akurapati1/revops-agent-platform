"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

export function useFetch<T>(path: string | null, opts: { interval?: number | (() => number | false) } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef(opts.interval);
  intervalRef.current = opts.interval;

  const load = useCallback(async (silent = false) => {
    if (!path) return;
    if (!silent) setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const tick = () => {
      const iv = typeof intervalRef.current === "function" ? intervalRef.current() : intervalRef.current;
      if (!iv || stopped) return;
      timer = setTimeout(async () => {
        await load(true);
        tick();
      }, iv);
    };
    tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [load, path]);

  return { data, error, loading, reload: () => load(true), setData };
}
