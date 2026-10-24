"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import { useSession } from "./session";
import type { CardEnvelope, FeedItem } from "./types";

export function readDemo(): api.DemoState {
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("demo");
  return v === "denied" || v === "limit" || v === "error" || v === "empty" ? v : null;
}

export type LoadState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: api.ApiError | Error };

function useLoad<T>(key: string | null, load: () => Promise<T>) {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{ key: string; value: LoadState<T> } | null>(null);
  const fullKey = key === null ? null : `${key}#${nonce}`;

  useEffect(() => {
    if (fullKey === null) return;
    let live = true;
    load()
      .then((data) => live && setResult({ key: fullKey, value: { status: "ready", data } }))
      .catch((error) => live && setResult({ key: fullKey, value: { status: "error", error } }));
    return () => {
      live = false;
    };
  }, [fullKey]);

  const state: LoadState<T> = result && result.key === fullKey ? result.value : { status: "loading" };
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { state, reload };
}

export function useFeed() {
  const { company, role, switching } = useSession();
  const companyId = company?.id ?? null;
  const { state, reload } = useLoad<FeedItem[]>(companyId ? `${companyId}:${role}` : null, () =>
    api.getFeed(companyId as string, role, readDemo()),
  );
  const loading = switching || state.status === "loading";
  return { state, loading, reload };
}

export function useCard(id: string) {
  const { role, company } = useSession();
  const companyId = company?.id ?? null;

  return useLoad<CardEnvelope>(
    companyId ? `${id}:${role}:${companyId}` : null,
    () => api.getCard(id, role, companyId as string, readDemo())
  );
}