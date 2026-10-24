/**
 * Типы данных фронтенда.
 *
 * Карточка (`Insight`) повторяет prompts/schemas/insight.json (ветка llm): названия и допустимые значения
 * полей взяты оттуда. Всё, чего в схеме нет (ID, дата, источники с названиями, признак проверки критиком),
 * лежит в обёртке `CardEnvelope`. Формат обёртки пока наше допущение, его подтвердит бэкенд.
 */

export type OverallImpact = "negative" | "positive" | "mixed" | "neutral";
export type Materiality = "high" | "medium" | "low";
export type SourceBasis = "bank_analytics" | "mixed" | "external_only";
export type Confidence = "high" | "medium" | "low";
export type ClaimStatus = "confirmed" | "reported" | "speculative";

export type FactorCode =
  | "KEY_RATE"
  | "INFLATION"
  | "FX"
  | "SANCTIONS_TRADE"
  | "COMMODITIES"
  | "TAX_REGULATION"
  | "GOV_SPENDING"
  | "CONSUMER_DEMAND"
  | "LABOR_MARKET"
  | "CREDIT_DEBT_MARKET"
  | "ECONOMIC_GROWTH"
  | "LOGISTICS"
  | "INDUSTRY_EVENT"
  | "REGIONAL_EVENT"
  | "CORPORATE_EVENT";

export type RoleCode =
  | "owner"
  | "ceo"
  | "cfo"
  | "treasurer"
  | "chief_accountant"
  | "c_level"
  | "other";

export type ScenarioName = "базовый" | "негативный" | "позитивный";
export type ScenarioLikelihood = "более вероятный" | "возможный" | "маловероятный";
export type ActionType = "analysis" | "operational" | "bank_product";
export type ContactKind = "contact_manager" | "request" | "callback";

export interface WhyRelevant {
  feature: string;
  factor: FactorCode;
  explanation: string;
}

export interface WhatHappened {
  text: string;
  source_ids: string[];
  status: ClaimStatus;
}

export interface BankView {
  text: string;
  thesis_id: string;
  report: string;
  report_date: string;
}

export interface Conclusion {
  text: string;
  based_on: string[];
  confidence: "high" | "medium";
}

export interface Hypothesis {
  text: string;
  based_on: string[];
  confidence: "medium" | "low";
  how_to_check: string;
}

export interface RiskOrOpportunity {
  text: string;
  based_on: string[];
  confidence: Confidence;
}

export interface Scenario {
  name: ScenarioName;
  text: string;
  trigger: string;
  logic: string;
  likelihood: ScenarioLikelihood;
}

export interface Action {
  text: string;
  type: ActionType;
  product: string | null;
  rule_id: string | null;
  cta: ContactKind | null;
}

export interface ImpactEstimate {
  metric: string;
  range: string;
  method: string;
  based_on: string[];
  confidence: "medium" | "low";
}

export interface Impact {
  criterion: string;
  estimate: ImpactEstimate | null;
  no_estimate_reason: string | null;
}

export interface Insight {
  headline: string;
  overall_impact: OverallImpact;
  materiality: Materiality;
  impact: Impact;
  source_basis: SourceBasis;
  why_relevant: WhyRelevant[];
  what_happened: WhatHappened[];
  bank_view: BankView[];
  ai_conclusions: Conclusion[];
  hypotheses: Hypothesis[];
  risks: RiskOrOpportunity[];
  opportunities: RiskOrOpportunity[];
  scenarios: Scenario[];
  actions: Action[];
  open_questions: string[];
  role: RoleCode;
  /** Ставит система, не модель: обязателен при source_basis = external_only */
  badge?: string | null;
  /** Ставит система фиксированным текстом (disclaimers.yaml) */
  disclaimer?: string;
}

/* ---------- Обёртка вокруг карточки (допущение, ждёт подтверждения от бэкенда) ---------- */

export type SourceKind = "news" | "regulator" | "bank_report" | "external";

export interface SourceInfo {
  id: string;
  kind: SourceKind;
  title: string;
  outlet?: string;
  date?: string;
  url?: string;
}

export interface CardEnvelope {
  id: string;
  companyId: string;
  createdAt: string;
  isNew: boolean;
  primaryFactor: FactorCode;
  /** Прошла ли карточка проверку критиком. Не прошедшие пользователю не показываются */
  criticPassed: boolean;
  card: Insight;
  /** Источники, на которые ссылаются коды в карточке (news:…, T-…, ext:…) */
  sources: Record<string, SourceInfo>;
  /** Шаги агента для экрана «Как получен вывод» */
  trace?: TraceStep[];
}

export interface TraceStep {
  title: string;
  detail: string;
  features?: string[];
  note?: string;
}

export interface FeedItem {
  id: string;
  headline: string;
  overallImpact: OverallImpact;
  materiality: Materiality;
  factor: FactorCode;
  createdAt: string;
  isNew: boolean;
  external: boolean;
  whyLine: string;
  sourceLine: string;
}

/* ---------- Люди и компании ---------- */

export interface Company {
  id: string;
  short: string;
  name: string;
  /** Короткая метка: «Производство · Группа 1» */
  label: string;
  /** Полный вид деятельности для подсказки */
  activity: string;
  group: string;
  newEvents: number;
}

export interface Person {
  fullName: string;
  initials: string;
}

export interface Me {
  person: Person;
  companies: Company[];
  lastCompanyId: string | null;
}

export interface RejectedCard {
  id: string;
  headline: string;
  factor: string;
  issues: string[];
}

export type FeedbackKind = "useful" | "not_important" | "error";
