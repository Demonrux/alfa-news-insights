import type { CardEnvelope, FeedItem, Me, RoleCode, RejectedCard } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export type DemoState = "denied" | "limit" | "error" | "empty" | null;

async function fetcher<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });

  if (!res.ok) {
    if (res.status === 403) throw new ApiError(403, "Нет доступа");
    if (res.status === 429) throw new ApiError(429, "Лимит");
    if (res.status === 422) throw new ApiError(422, "Ошибка валидации");
    if (res.status === 404) throw new ApiError(404, "Не найдено");
    throw new ApiError(res.status, "Ошибка сети");
  }
  return res.json();
}

export async function login(phone: string, password: string): Promise<Me> {
  return fetcher<Me>("/api/login", {
    method: "POST",
    body: JSON.stringify({ person_id: "F_67674" }),
  });
}

export async function getMe(): Promise<Me> {
  return fetcher<Me>("/api/login", {
    method: "POST",
    body: JSON.stringify({ person_id: "F_67674" }),
  });
}

export function defaultRole(companyId: string): RoleCode {
  return "cfo";
}

export async function getFeed(companyId: string, role: RoleCode, demo: DemoState = null): Promise<FeedItem[]> {
  return fetcher<FeedItem[]>(`/api/feed?client_id=${encodeURIComponent(companyId)}&role=${role}`);
}

export async function getCard(id: string, role: RoleCode, companyId: string, demo: DemoState = null): Promise<CardEnvelope> {
  const env = await fetcher<CardEnvelope>("/api/insights", {
    method: "POST",
    body: JSON.stringify({ event_id: id, company_id: companyId, role }),
  });

  if (!env.card) throw new ApiError(422, (env as any).reason || "Не удалось сгенерировать карточку");
  return env;
}

export async function getRejected(): Promise<RejectedCard[]> {
  return [
    {
      id: "rej-1",
      headline: "Рост тарифов на электроэнергию снизит маржу производства",
      factor: "Отраслевое событие",
      issues: ["Новость касается другого региона, профиль компании это не подтверждает.", "Предположение о марже подано как факт."],
    },
    {
      id: "rej-2",
      headline: "[Заголовок отклонённого вывода]",
      factor: "Ключевая ставка",
      issues: ["Позиция банка приведена без ссылки на отчёт."],
    },
  ];
}

export async function sendFeedback(cardId: string, kind: any): Promise<void> {}
export async function submitContact(cardId: string | null, kind: any, comment: string): Promise<void> {}