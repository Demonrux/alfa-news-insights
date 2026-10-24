"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import { useSession } from "./session";
import type { CardEnvelope, FeedItem } from "./types";

/** Состояние для показа на демо: ?demo=denied | limit | error | empty */
export function readDemo(): api.DemoState {
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("demo");
  return v === "denied" || v === "limit" || v === "error" || v === "empty" ? v : null;
}

export type LoadState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: api.ApiError | Error };

/**
 * Загрузка данных по ключу. Результат хранится вместе с ключом запроса: пока ключ другой, показываем
 * «загрузка», и не нужно сбрасывать состояние внутри эффекта. reload() делает новый запрос с тем же ключом.
 */
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
    // load меняется вместе с ключом, поэтому отдельно в зависимости его не включаем
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullKey]);

  const state: LoadState<T> = result && result.key === fullKey ? result.value : { status: "loading" };
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { state, reload };
}

/** Лента событий выбранной компании и роли. При смене компании или роли загружается заново */
export function useFeed() {
  const { company, role, switching } = useSession();
  const companyId = company?.id ?? null;
  const { state, reload } = useLoad<FeedItem[]>(companyId ? `${companyId}:${role}` : null, () =>
    api.getFeed(companyId as string, role, readDemo()),
  );
  const loading = switching || state.status === "loading";
  return { state, loading, reload };
}

/** Одна карточка для выбранной роли */
export function useCard(id: string) {
  const { role } = useSession();
  return useLoad<CardEnvelope>(`${id}:${role}`, () => api.getCard(id, role, readDemo()));
}
