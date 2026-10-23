/**
 * Словари «код → подпись». Источники: prompts/taxonomy.yaml (факторы), prompts/feature_dictionary.yaml
 * (признаки компании), prompts/disclaimers.yaml (типы утверждений).
 */
import type {
  ActionType,
  Confidence,
  ContactKind,
  FactorCode,
  Materiality,
  OverallImpact,
  RoleCode,
  ScenarioLikelihood,
  SourceBasis,
  SourceKind,
} from "./types";

export const FACTOR_LABEL: Record<FactorCode, string> = {
  KEY_RATE: "Ключевая ставка",
  INFLATION: "Инфляция",
  FX: "Курс рубля",
  SANCTIONS_TRADE: "Санкции и внешняя торговля",
  COMMODITIES: "Сырьё",
  TAX_REGULATION: "Налоги и регулирование",
  GOV_SPENDING: "Госрасходы и госзаказ",
  CONSUMER_DEMAND: "Потребительский спрос",
  LABOR_MARKET: "Рынок труда",
  CREDIT_DEBT_MARKET: "Кредитный и долговой рынок",
  ECONOMIC_GROWTH: "Рост экономики",
  LOGISTICS: "Логистика",
  INDUSTRY_EVENT: "Отраслевое событие",
  REGIONAL_EVENT: "Региональное событие",
  CORPORATE_EVENT: "Событие у компании",
};

/** Роли, которые показываем в интерфейсе. Остальные значения схемы сводим к ближайшей */
export const UI_ROLES: { code: RoleCode; name: string; focus: string }[] = [
  { code: "cfo", name: "Финансовый директор", focus: "Долговая нагрузка, бюджет, план движения денег" },
  { code: "treasurer", name: "Руководитель казначейства", focus: "Ликвидность, ставки, курсы валют" },
  { code: "ceo", name: "Генеральный директор", focus: "Стратегия, инвестпроекты, спрос" },
  { code: "owner", name: "Собственник бизнеса", focus: "Прибыль группы и ключевые риски" },
];

const ROLE_FALLBACK: Record<RoleCode, RoleCode> = {
  cfo: "cfo",
  treasurer: "treasurer",
  ceo: "ceo",
  owner: "owner",
  chief_accountant: "cfo",
  c_level: "ceo",
  other: "ceo",
};

export function uiRole(code: RoleCode): RoleCode {
  return ROLE_FALLBACK[code];
}

export function roleName(code: RoleCode): string {
  const ui = uiRole(code);
  return UI_ROLES.find((r) => r.code === ui)?.name ?? "Руководитель";
}

/** Признаки компании из feature:CODE → человеческая подпись */
export const FEATURE_LABEL: Record<string, string> = {
  CL_PRODUCT_RKO_MARK: "Расчётно-кассовое обслуживание в банке",
  CL_PRODUCT_LOA_MARK: "Кредиты в банке",
  CL_PRODUCT_LEA_MARK: "Лизинг в банке",
  CL_PRODUCT_DEP_MARK: "Депозиты в банке",
  CL_PRODUCT_GAR_MARK: "Банковские гарантии",
  CL_PRODUCT_ZPP_MARK: "Зарплатный проект",
  FACTORING_MARK: "Факторинг",
  FTS_FLAG: "Внешнеэкономическая деятельность",
  MAINOKVED_NAME: "Вид деятельности",
  REVENUE_COMPANY: "Масштаб выручки",
  REGION: "Регион",
};

/** Подпись для кода-ссылки (feature:…, cp:…, news:…, T-…): то, что можно показать пользователю */
export function refLabel(code: string): string {
  if (code.startsWith("feature:")) {
    const key = code.slice("feature:".length);
    return FEATURE_LABEL[key] ?? "Признак компании";
  }
  if (code.startsWith("cp:")) return "Контрагенты компании";
  if (code.startsWith("news:") || code.startsWith("ext:")) return "Новость";
  if (/^T-[A-Z0-9]+-\d{2}$/.test(code)) return "Позиция банка";
  if (code.startsWith("chunk:")) return "Отчёт банка";
  return "Источник";
}

export const OVERALL_IMPACT_LABEL: Record<OverallImpact, string> = {
  negative: "Риск",
  positive: "Возможность",
  mixed: "Смешанное",
  neutral: "Нейтрально",
};

export const MATERIALITY_LABEL: Record<Materiality, string> = {
  high: "Высокое",
  medium: "Среднее",
  low: "Низкое",
};

export const MATERIALITY_LEVEL: Record<Materiality, 1 | 2 | 3> = { low: 1, medium: 2, high: 3 };

/** Подписи типов утверждений: disclaimers.yaml → labels */
export const CLAIM_LABEL = {
  fact: "Факт",
  bank: "Позиция Альфа-Банка",
  ai: "Вывод AI",
  hypothesis: "Гипотеза — требует проверки",
  estimate: "Оценка AI",
} as const;

export const CLAIM_HINT = {
  fact: "Подтверждено источником",
  bank: "Со ссылкой на отчёт банка",
  ai: "Сформировано моделью, не официальная позиция банка",
  hypothesis: "Предположение, не подтверждено",
} as const;

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: "Высокая уверенность",
  medium: "Средняя уверенность",
  low: "Низкая уверенность",
};

export const LIKELIHOOD_LABEL: Record<ScenarioLikelihood, string> = {
  "более вероятный": "Более вероятный",
  возможный: "Возможный",
  маловероятный: "Маловероятный",
};

export const ACTION_TYPE_LABEL: Record<ActionType, string> = {
  analysis: "Анализ",
  operational: "Действие",
  bank_product: "Продукт банка",
};

export const CTA_LABEL: Record<ContactKind, string> = {
  contact_manager: "Связаться с менеджером",
  request: "Оставить заявку",
  callback: "Заказать звонок",
};

export const CTA_SUBMIT: Record<ContactKind, string> = {
  contact_manager: "Отправить",
  request: "Отправить заявку",
  callback: "Заказать звонок",
};

export const SOURCE_KIND_LABEL: Record<SourceKind, string> = {
  news: "Новость",
  regulator: "Регулятор",
  bank_report: "Отчёт банка",
  external: "Внешний источник",
};

/** Подписи основания ответа в чате (chat.json → basis) */
export const CHAT_BASIS_LABEL: Record<string, string> = {
  bank_analytics: "Отчёт банка",
  mixed: "Отчёт банка и новость",
  external_only: "Внешний источник",
  ai_scenario: "Сценарий AI, не прогноз банка",
  no_data: "Недостаточно данных",
};

/** Фиксированные тексты. В бою дисклеймер и бейдж приходят из ответа API, это запасной вариант */
export const DISCLAIMER_ALWAYS =
  "Материал носит информационный характер и не является инвестиционной рекомендацией.";

export const DISCLAIMER_BY_BASIS: Record<SourceBasis, string> = {
  bank_analytics:
    "Выводы основаны на аналитике Центра макроэкономических исследований Альфа-Банка и данных о вашей компании.",
  mixed:
    "Позиция ЦМИ Альфа-Банка отмечена отдельно. Остальные выводы сформированы AI и не являются официальной позицией банка.",
  external_only:
    "Не является позицией банка: вывод сформирован AI на основе внешних источников без поддержки аналитики ЦМИ Альфа-Банка.",
};

export const BADGE_EXTERNAL = "Не является позицией банка";

/** Фильтры ленты: набор факторов, которые показываем отдельными пунктами */
export const FEED_FACTOR_FILTERS: FactorCode[] = [
  "KEY_RATE",
  "INFLATION",
  "FX",
  "TAX_REGULATION",
  "CONSUMER_DEMAND",
  "LOGISTICS",
  "LABOR_MARKET",
];
