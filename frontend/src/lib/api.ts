/**
 * Единственное место, где фронт обращается за данными.
 *
 * Пока бэкенд не готов, функции отдают моки (src/mocks/data.ts) с небольшой задержкой. Когда API появится,
 * меняется только тело функций: экраны работают с теми же типами. Адрес API задаётся переменной
 * NEXT_PUBLIC_API_URL (см. .env.example).
 *
 * Ошибки по кодам ответов API (403, 429, 422, 502) приходят как ApiError, экраны показывают нужное состояние.
 */
import {
  MOCK_CARDS,
  MOCK_DEFAULT_ROLES,
  MOCK_FEED_BY_COMPANY,
  MOCK_ME,
  MOCK_REJECTED,
} from "@/mocks/data";
import { uiRole } from "./labels";
import type {
  CardEnvelope,
  ContactKind,
  FeedbackKind,
  FeedItem,
  Me,
  RoleCode,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: 403 | 404 | 422 | 429 | 502,
    message: string,
  ) {
    super(message);
  }
}

/** Принудительные состояния для показа на демо: ?demo=denied | limit | error | empty */
export type DemoState = "denied" | "limit" | "error" | "empty" | null;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function checkDemo(demo: DemoState) {
  if (demo === "denied") throw new ApiError(403, "Нет доступа к событиям этой компании");
  if (demo === "limit") throw new ApiError(429, "Новые разборы сегодня недоступны");
  if (demo === "error") throw new ApiError(502, "Не удалось загрузить события");
}

/** В демо подойдут любые данные, в том числе пустые: жюри не должно упираться в форму */
export async function login(phone: string, password: string): Promise<Me> {
  await sleep(300);
  void phone;
  void password;
  return MOCK_ME;
}

export async function getMe(): Promise<Me> {
  await sleep(150);
  return MOCK_ME;
}

export function defaultRole(companyId: string): RoleCode {
  return MOCK_DEFAULT_ROLES[companyId] ?? "cfo";
}

/** Карточка для роли: для карточки про ставку есть отдельные варианты по ролям, остальные подстраиваем */
function forRole(env: CardEnvelope, role: RoleCode): CardEnvelope {
  const ui = uiRole(role);
  if (env.id === "card-rate-cfo" || env.id === "card-rate-treasurer") {
    const wanted = ui === "treasurer" ? "card-rate-treasurer" : "card-rate-cfo";
    const pick = MOCK_CARDS.find((c) => c.id === wanted) ?? env;
    return { ...pick, id: env.id, companyId: env.companyId, card: { ...pick.card, role: ui } };
  }
  return { ...env, card: { ...env.card, role: ui } };
}

function toFeedItem(env: CardEnvelope): FeedItem {
  const { card } = env;
  const outlets = Object.values(env.sources)
    .filter((s) => s.kind !== "bank_report")
    .map((s) => s.outlet)
    .filter(Boolean) as string[];
  const parts = [...new Set(outlets)];
  if (card.bank_view.length > 0) parts.push("аналитика Альфа-Банка");
  return {
    id: env.id,
    headline: card.headline,
    overallImpact: card.overall_impact,
    materiality: card.materiality,
    factor: env.primaryFactor,
    createdAt: env.createdAt,
    isNew: env.isNew,
    external: card.source_basis === "external_only",
    whyLine: card.why_relevant[0]?.explanation ?? "",
    sourceLine: parts.length ? `Источник: ${parts.join(", ")}` : "",
  };
}

export async function getFeed(companyId: string, role: RoleCode, demo: DemoState = null): Promise<FeedItem[]> {
  await sleep(500);
  checkDemo(demo);
  if (demo === "empty") return [];
  const ids = MOCK_FEED_BY_COMPANY[companyId] ?? [];
  return ids
    .map((id) => MOCK_CARDS.find((c) => c.id === id))
    .filter((c): c is CardEnvelope => !!c && c.criticPassed)
    .map((c) => toFeedItem(forRole(c, role)));
}

/** Ответ POST /cards заняла бы до минуты: на мока имитируем несколько секунд, чтобы показать шаги агента */
export async function getCard(id: string, role: RoleCode, demo: DemoState = null): Promise<CardEnvelope> {
  await sleep(700);
  checkDemo(demo);
  const env = MOCK_CARDS.find((c) => c.id === id);
  if (!env) throw new ApiError(404, "Карточка не найдена");
  return forRole(env, role);
}

export async function getRejected() {
  await sleep(200);
  return MOCK_REJECTED;
}

/* ---------- Действия пользователя (пока ни на что не влияют, кроме локального состояния) ---------- */

export async function sendFeedback(cardId: string, kind: FeedbackKind): Promise<void> {
  await sleep(150);
  void cardId;
  void kind;
}

export async function submitContact(
  cardId: string | null,
  kind: ContactKind,
  comment: string,
): Promise<void> {
  await sleep(400);
  void cardId;
  void kind;
  void comment;
}
