"use client";

import { useCallback, useEffect, useState } from "react";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

const OFFLINE =
  "Cannot reach the analysis backend. Start it from the repository root with " +
  "`.venv/bin/uvicorn backend.main:app --port 8000`, then retry.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch {
    throw new ApiError(OFFLINE, 0);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body: the dev proxy answers this way when the backend is down */
    }
    // 502/503/504, or a 500 with no JSON detail, means the request never reached FastAPI.
    if (!detail && res.status >= 500) throw new ApiError(OFFLINE, res.status);
    throw new ApiError(detail || res.statusText || `Request failed (${res.status})`, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// GET responses are immutable for a given backend run, so cache them for the session.
const cache = new Map<string, unknown>();
const inflight = new Map<string, Promise<unknown>>();

function load<T>(path: string): Promise<T> {
  if (cache.has(path)) return Promise.resolve(cache.get(path) as T);
  if (!inflight.has(path)) {
    inflight.set(
      path,
      api
        .get<T>(path)
        .then((d) => {
          cache.set(path, d);
          return d;
        })
        .finally(() => inflight.delete(path)),
    );
  }
  return inflight.get(path) as Promise<T>;
}

export interface Resource<T> {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  retry: () => void;
}

export function useApi<T>(path: string | null): Resource<T> {
  const [state, setState] = useState<{ data?: T; error?: ApiError; path?: string | null }>(() =>
    path && cache.has(path) ? { data: cache.get(path) as T, path } : {},
  );
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!path) return;
    let live = true;
    if (cache.has(path)) {
      setState({ data: cache.get(path) as T, path });
      return;
    }
    setState((s) => ({ data: s.path === path ? s.data : undefined, path }));
    load<T>(path)
      .then((data) => live && setState({ data, path }))
      .catch((error: ApiError) => live && setState({ error, path }));
    return () => {
      live = false;
    };
  }, [path, attempt]);

  const retry = useCallback(() => {
    if (path) cache.delete(path);
    setAttempt((a) => a + 1);
  }, [path]);

  const current = state.path === path;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: !!path && (!current || (!state.data && !state.error)),
    retry,
  };
}
