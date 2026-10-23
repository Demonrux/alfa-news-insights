/**
 * Моки для разработки без бэкенда.
 *
 * - card-rate-treasurer.json: живой вывод модели (prompts p5_interpret, Настя, 22.10.2026) без правок.
 * - Остальные карточки синтетические: написаны под схему insight.json, чтобы проверить интерфейс на разных
 *   случаях (с позицией банка и без, нейтральное влияние, разные роли). Тексты в квадратных скобках — плейсхолдеры.
 *
 * Когда появится настоящий API, этот файл остаётся только для тестов и демо без сети.
 */
import live from "./card-rate-treasurer.json";
import {
  BADGE_EXTERNAL,
  DISCLAIMER_ALWAYS,
  DISCLAIMER_BY_BASIS,
  FACTOR_LABEL,
  refLabel,
} from "@/lib/labels";
import type {
  CardEnvelope,
  Company,
  Insight,
  Me,
  RoleCode,
  SourceInfo,
  TraceStep,
} from "@/lib/types";

/* ---------- Люди и компании ---------- */

export const MOCK_ME: Me = {
  person: { fullName: "Иван Иванович Иванов", initials: "ИИ" },
  lastCompanyId: null,
  companies: [
    {
      id: "c1",
      short: "К1",
      name: "Компания 1",
      label: "Производство · Группа 1",
      activity: "Производство строительных материалов",
      group: "Группа компаний 1",
      newEvents: 3,
    },
    {
      id: "c2",
      short: "К2",
      name: "Компания 2",
      label: "Логистика · Группа 1",
      activity: "Грузовые перевозки и складская логистика",
      group: "Группа компаний 1",
      newEvents: 1,
    },
    {
      id: "c3",
      short: "К3",
      name: "Компания 3",
      label: "Оптовая торговля · Группа 1",
      activity: "Оптовая торговля строительными материалами",
      group: "Группа компаний 1",
      newEvents: 0,
    },
    {
      id: "c4",
      short: "К4",
      name: "Компания 4",
      label: "Производство · Группа 2",
      activity: "Производство упаковки из картона и пластика",
      group: "Группа компаний 2",
      newEvents: 0,
    },
  ] satisfies Company[],
};

/** Роль по умолчанию для каждой компании в демо */
export const MOCK_DEFAULT_ROLES: Record<string, RoleCode> = { c1: "cfo", c2: "treasurer", c3: "owner", c4: "cfo" };

/* ---------- Источники ---------- */

const NEWS_RATE: SourceInfo = {
  id: "news:s001",
  kind: "news",
  title: "Банк России сохранил ключевую ставку на уровне 14%",
  outlet: "[Издание]",
  date: "2026-09-11",
  url: "#",
};
const REG_RATE: SourceInfo = {
  id: "ext:cbr-2026-09-11",
  kind: "regulator",
  title: "Пресс-релиз Банка России о ключевой ставке",
  outlet: "Банк России",
  date: "2026-09-11",
  url: "#",
};
const BANK_RATE_TITLE = "Ключевая ставка ЦБ РФ: ставка без изменения на 14,0%, риторика стала жестче";
const THESES: Record<string, SourceInfo> = {
  "T-RATE-01": { id: "T-RATE-01", kind: "bank_report", title: BANK_RATE_TITLE, date: "2026-09-11", url: "#" },
  "T-RATE-02": { id: "T-RATE-02", kind: "bank_report", title: BANK_RATE_TITLE, date: "2026-09-11", url: "#" },
  "T-STR-05": {
    id: "T-STR-05",
    kind: "bank_report",
    title: "Тактический взгляд на 3-й квартал 2026 года: время собирать камни",
    url: "#",
  },
  "T-BOND-01": { id: "T-BOND-01", kind: "bank_report", title: "Бонд Бриф: итоги недели", url: "#" },
  "T-CONS-01": { id: "T-CONS-01", kind: "bank_report", title: "Потребление на пике", date: "2026-08-28", url: "#" },
  "T-LAB-01": {
    id: "T-LAB-01",
    kind: "bank_report",
    title: "Макростатистика 7М26: данные по рынку труда не подтверждают охлаждения экономики",
    date: "2026-09-04",
    url: "#",
  },
};

function srcMap(...items: SourceInfo[]): Record<string, SourceInfo> {
  return Object.fromEntries(items.map((s) => [s.id, s]));
}

/* ---------- Помощники ---------- */

function ago(days: number, hours = 10, minutes = 40): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

/** Дисклеймер и бейдж ставит система, а не модель: имитируем это здесь */
function finalize(i: Omit<Insight, "badge" | "disclaimer">): Insight {
  const external = i.source_basis === "external_only";
  return {
    ...i,
    badge: external ? BADGE_EXTERNAL : null,
    disclaimer: `${DISCLAIMER_ALWAYS} ${DISCLAIMER_BY_BASIS[i.source_basis]}`,
  };
}

function makeTrace(card: Insight, roleNote: string): TraceStep[] {
  const features = [...new Set(card.why_relevant.map((w) => refLabel(w.feature)))];
  const factor = FACTOR_LABEL[card.why_relevant[0]?.factor ?? "KEY_RATE"];
  return [
    { title: "Нашли событие", detail: `Фактор: ${factor.toLowerCase()}. Новости и официальные публикации за последние дни.` },
    {
      title: "Сверили с аналитикой банка",
      detail:
        card.bank_view.length > 0
          ? `Нашли ${card.bank_view.length} тезис(а) в отчёте «${card.bank_view[0].report}».`
          : "Позиции банка по теме не нашли. Карточка получила пометку «Не является позицией банка».",
    },
    {
      title: "Сопоставили с профилем компании",
      detail: "Точные суммы и идентификаторы компании в анализ не передаются.",
      features,
    },
    { title: "Сформировали вывод для роли", detail: roleNote },
    {
      title: "Проверка критиком",
      detail: "Второй агент сверил вывод с источниками и проверил, что факты и предположения разделены.",
      note: "Замечаний нет.",
    },
  ];
}

function envelope(
  id: string,
  companyId: string,
  daysAgo: number,
  isNew: boolean,
  card: Insight,
  sources: Record<string, SourceInfo>,
  roleNote: string,
): CardEnvelope {
  return {
    id,
    companyId,
    createdAt: ago(daysAgo, 10, 40),
    isNew,
    primaryFactor: card.why_relevant[0].factor,
    criticPassed: true,
    card,
    sources,
    trace: makeTrace(card, roleNote),
  };
}

/* ---------- Карточки ---------- */

const rateTreasurer: Insight = {
  ...(live as unknown as Insight),
  badge: null,
  disclaimer: `${DISCLAIMER_ALWAYS} ${DISCLAIMER_BY_BASIS.mixed}`,
};

const rateCfo: Insight = finalize({
  headline: "Кредиты останутся дорогими дольше: нагрузка по плавающим ставкам не снизится",
  overall_impact: "negative",
  materiality: "high",
  impact: {
    criterion: "Событие напрямую меняет стоимость действующих кредитов компании.",
    estimate: {
      metric: "Процентные расходы по плавающим кредитам",
      range: "[диапазон, ₽ в год]",
      method: "[метод расчёта по условиям договоров]",
      based_on: ["feature:CL_PRODUCT_LOA_MARK", "T-RATE-02"],
      confidence: "low",
    },
    no_estimate_reason: null,
  },
  source_basis: "bank_analytics",
  why_relevant: [
    { feature: "feature:CL_PRODUCT_LOA_MARK", factor: "KEY_RATE", explanation: "У компании есть кредиты, стоимость которых зависит от ставки" },
    { feature: "feature:MAINOKVED_NAME", factor: "CREDIT_DEBT_MARKET", explanation: "Производство требует длинного финансирования инвестиций" },
  ],
  what_happened: [
    { text: "11 сентября 2026 года Совет директоров Банка России сохранил ключевую ставку на уровне 14% годовых", source_ids: ["news:s001"], status: "confirmed" },
    { text: "Это первая пауза в цикле смягчения после десяти последовательных снижений, начавшегося в июне 2025 года", source_ids: ["news:s001"], status: "confirmed" },
  ],
  bank_view: [
    { thesis_id: "T-RATE-01", report: BANK_RATE_TITLE, report_date: "2026-09-11", text: "ЦБ сохранил ключевую ставку на 14,0%, но риторика ужесточилась: совет директоров обсуждал только паузу, снижение не рассматривалось." },
    { thesis_id: "T-RATE-02", report: BANK_RATE_TITLE, report_date: "2026-09-11", text: "ЦМИ ожидает сохранения ставки на заседании 23 октября и до конца 2026 года на уровне 14,0%." },
  ],
  ai_conclusions: [
    { text: "Для вас это сигнал, что быстрое удешевление кредитов временно остановилось: платежи по кредитам с плавающей ставкой в ближайшие месяцы останутся на текущем уровне.", based_on: ["news:s001", "feature:CL_PRODUCT_LOA_MARK", "T-RATE-02"], confidence: "high" },
    { text: "Текущую стоимость долга стоит закладывать в бюджет и план движения денег, а не рассчитывать на скорое снижение.", based_on: ["feature:CL_PRODUCT_LOA_MARK", "T-RATE-01"], confidence: "medium" },
  ],
  hypotheses: [
    { text: "Если пауза затянется, часть инвестпроектов на заёмные средства придётся пересмотреть по срокам.", based_on: ["feature:MAINOKVED_NAME", "T-RATE-02"], confidence: "low", how_to_check: "Сверить график инвестиций с условиями кредитных договоров" },
  ],
  risks: [
    { text: "Процентные расходы не снизятся в плановом периоде", based_on: ["feature:CL_PRODUCT_LOA_MARK", "T-RATE-02"], confidence: "high" },
    { text: "Бюджет на обслуживание долга придётся держать на текущем уровне", based_on: ["feature:CL_PRODUCT_LOA_MARK"], confidence: "medium" },
  ],
  opportunities: [
    { text: "Есть время заранее обсудить условия будущих траншей и пересмотр ставки", based_on: ["feature:CL_PRODUCT_LOA_MARK", "T-RATE-01"], confidence: "medium" },
  ],
  scenarios: [
    { name: "базовый", text: "Ставка остаётся на текущем уровне до конца года. Платежи по плавающим кредитам не меняются.", trigger: "ЦБ подтвердит паузу на заседании 23 октября", logic: "Риторика регулятора указывает на приоритет борьбы с инфляцией", likelihood: "более вероятный" },
    { name: "позитивный", text: "Снижение ставки возобновится позже. Нагрузка начнёт снижаться с задержкой на срок пересмотра ставки по договору.", trigger: "Замедление инфляции по данным за несколько месяцев", logic: "Регулятор вернётся к смягчению при устойчивом замедлении цен", likelihood: "возможный" },
    { name: "негативный", text: "Ставку повысят. Платежи по плавающим кредитам вырастут.", trigger: "Ускорение инфляции выше ожиданий", logic: "Ужесточившаяся риторика допускает повышение", likelihood: "маловероятный" },
  ],
  actions: [
    { text: "Обсудить с менеджером, как снизить зависимость от плавающей ставки", type: "bank_product", product: "хеджирование процентного риска", rule_id: "A-RATE-LOA", cta: "contact_manager" },
    { text: "Пересчитать план движения денег на текущей стоимости долга", type: "analysis", product: null, rule_id: null, cta: null },
  ],
  open_questions: ["Когда по вашим договорам пересматривается плавающая ставка?", "Какая доля долга приходится на плавающие ставки?"],
  role: "cfo",
});

const fxYuan: Insight = finalize({
  headline: "Колебания курса юаня меняют стоимость закупок импортного оборудования",
  overall_impact: "mixed",
  materiality: "medium",
  impact: { criterion: "Курс влияет на рублёвую стоимость импортных закупок компании.", estimate: null, no_estimate_reason: "Нет данных о графике и объёме закупок в юанях" },
  source_basis: "external_only",
  why_relevant: [{ feature: "feature:FTS_FLAG", factor: "FX", explanation: "Компания ведёт внешнеэкономическую деятельность и закупает оборудование за рубежом" }],
  what_happened: [{ text: "Курс юаня к рублю за неделю заметно изменился по данным торгов", source_ids: ["ext:cny-week"], status: "reported" }],
  bank_view: [],
  ai_conclusions: [{ text: "Закупки оборудования в юанях стоит привязать к конкретным датам платежей: цена в рублях зависит от курса в день оплаты.", based_on: ["ext:cny-week", "feature:FTS_FLAG"], confidence: "medium" }],
  hypotheses: [],
  risks: [{ text: "Рост курса удорожит ближайшие импортные платежи", based_on: ["ext:cny-week", "feature:FTS_FLAG"], confidence: "medium" }],
  opportunities: [{ text: "Снижение курса позволит купить валюту для будущих закупок дешевле", based_on: ["ext:cny-week", "feature:FTS_FLAG"], confidence: "low" }],
  scenarios: [],
  actions: [{ text: "Проверить график платежей за импорт и валютную позицию на ближайшие месяцы", type: "analysis", product: null, rule_id: null, cta: null }],
  open_questions: ["На какие даты запланированы платежи за импорт?"],
  role: "cfo",
});

const subsidies: Insight = finalize({
  headline: "Новые правила субсидирования могут удешевить инвестпроекты в вашей отрасли",
  overall_impact: "positive",
  materiality: "medium",
  impact: { criterion: "Субсидии могут снизить стоимость финансирования отраслевых проектов.", estimate: null, no_estimate_reason: "Условия программы пока не опубликованы полностью" },
  source_basis: "external_only",
  why_relevant: [{ feature: "feature:MAINOKVED_NAME", factor: "GOV_SPENDING", explanation: "Компания работает в отрасли, на которую рассчитана программа" }],
  what_happened: [{ text: "Правительство описало новые условия субсидирования отраслевых инвестпроектов", source_ids: ["ext:gov-subsidy"], status: "reported" }],
  bank_view: [],
  ai_conclusions: [{ text: "Если проект подходит под условия, его стоит проверить на право получения субсидии до запуска финансирования.", based_on: ["ext:gov-subsidy", "feature:MAINOKVED_NAME"], confidence: "medium" }],
  hypotheses: [{ text: "Часть планируемых проектов компании может подойти под программу", based_on: ["feature:MAINOKVED_NAME", "ext:gov-subsidy"], confidence: "low", how_to_check: "Сверить планы инвестиций с критериями программы" }],
  risks: [],
  opportunities: [{ text: "Субсидия может удешевить финансирование нового проекта", based_on: ["ext:gov-subsidy", "feature:MAINOKVED_NAME"], confidence: "medium" }],
  scenarios: [],
  actions: [{ text: "Оценить, подходят ли планируемые проекты под условия программы", type: "analysis", product: null, rule_id: null, cta: null }],
  open_questions: ["Какие проекты запланированы на ближайшие два года?"],
  role: "ceo",
});

const rail: Insight = finalize({
  headline: "Перевозки по железной дороге дорожают: затраты на доставку продукции вырастут",
  overall_impact: "negative",
  materiality: "low",
  impact: { criterion: "Тарифы влияют на логистические расходы компании.", estimate: null, no_estimate_reason: "Нет данных об объёме отгрузок по железной дороге" },
  source_basis: "external_only",
  why_relevant: [{ feature: "feature:MAINOKVED_NAME", factor: "LOGISTICS", explanation: "Компания отгружает продукцию по железной дороге" }],
  what_happened: [{ text: "Тарифы на железнодорожные перевозки повышены", source_ids: ["ext:rail-tariffs"], status: "confirmed" }],
  bank_view: [],
  ai_conclusions: [{ text: "Рост тарифов увеличит себестоимость доставки, эффект будет заметен в ближайшие отгрузки.", based_on: ["ext:rail-tariffs", "feature:MAINOKVED_NAME"], confidence: "medium" }],
  hypotheses: [],
  risks: [{ text: "Затраты на доставку вырастут быстрее цен на продукцию", based_on: ["ext:rail-tariffs"], confidence: "low" }],
  opportunities: [],
  scenarios: [],
  actions: [{ text: "Пересчитать логистические расходы на ближайший квартал", type: "operational", product: null, rule_id: null, cta: null }],
  open_questions: [],
  role: "cfo",
});

const consumption: Insight = finalize({
  headline: "Потребление на пике: спрос на вашу продукцию остаётся высоким",
  overall_impact: "positive",
  materiality: "medium",
  impact: { criterion: "Спрос покупателей определяет объём продаж компании.", estimate: null, no_estimate_reason: "Нет данных о чувствительности выручки к потребительскому спросу" },
  source_basis: "bank_analytics",
  why_relevant: [{ feature: "feature:MAINOKVED_NAME", factor: "CONSUMER_DEMAND", explanation: "Основная деятельность компании зависит от потребительского и строительного спроса" }],
  what_happened: [{ text: "Потребительская активность остаётся высокой по данным макростатистики", source_ids: ["ext:stat-consumption"], status: "reported" }],
  bank_view: [{ thesis_id: "T-CONS-01", report: "Потребление на пике", report_date: "2026-08-28", text: "[Тезис ЦМИ из отчёта «Потребление на пике»]" }],
  ai_conclusions: [{ text: "Высокий спрос поддерживает продажи в ближайшие месяцы, но пик потребления означает риск замедления позже.", based_on: ["T-CONS-01", "feature:MAINOKVED_NAME"], confidence: "medium" }],
  hypotheses: [],
  risks: [{ text: "После пика спрос может замедлиться", based_on: ["T-CONS-01"], confidence: "low" }],
  opportunities: [{ text: "Можно нарастить запасы и объёмы поставок, пока спрос высок", based_on: ["T-CONS-01", "feature:MAINOKVED_NAME"], confidence: "medium" }],
  scenarios: [],
  actions: [{ text: "Проверить, хватает ли запасов и мощностей на ближайший сезон", type: "operational", product: null, rule_id: null, cta: null }],
  open_questions: [],
  role: "ceo",
});

const labor: Insight = finalize({
  headline: "Рынок труда не подтверждает охлаждения экономики: расходы на персонал останутся высокими",
  overall_impact: "neutral",
  materiality: "low",
  impact: { criterion: "Рынок труда влияет и на спрос покупателей, и на расходы на персонал.", estimate: null, no_estimate_reason: null },
  source_basis: "bank_analytics",
  why_relevant: [{ feature: "feature:CL_PRODUCT_ZPP_MARK", factor: "LABOR_MARKET", explanation: "У компании есть зарплатный проект, расходы на персонал заметны" }],
  what_happened: [{ text: "Данные по рынку труда за семь месяцев не показали признаков охлаждения", source_ids: ["T-LAB-01"], status: "reported" }],
  bank_view: [{ thesis_id: "T-LAB-01", report: "Макростатистика 7М26: данные по рынку труда не подтверждают охлаждения экономики", report_date: "2026-09-04", text: "[Тезис ЦМИ из макростатистики 7М26]" }],
  ai_conclusions: [{ text: "Давление на зарплаты сохранится, это стоит учесть при планировании расходов на персонал.", based_on: ["T-LAB-01", "feature:CL_PRODUCT_ZPP_MARK"], confidence: "medium" }],
  hypotheses: [],
  risks: [],
  opportunities: [],
  scenarios: [],
  actions: [{ text: "Заложить индексацию зарплат в план на следующий квартал", type: "analysis", product: null, rule_id: null, cta: null }],
  open_questions: [],
  role: "cfo",
});

const RATE_SOURCES = srcMap(NEWS_RATE, REG_RATE, THESES["T-RATE-01"], THESES["T-RATE-02"], THESES["T-STR-05"], THESES["T-BOND-01"]);
const EXT = (id: string, title: string, outlet: string, days: number): SourceInfo => ({
  id,
  kind: "external",
  title,
  outlet,
  date: ago(days).slice(0, 10),
  url: "#",
});

/** Все карточки по ID. Для ленты каждой компании выбираются свои */
export const MOCK_CARDS: CardEnvelope[] = [
  envelope("card-rate-cfo", "c1", 0, true, rateCfo, RATE_SOURCES, "Финансовый директор: долговая нагрузка, бюджет, план движения денег"),
  envelope("card-fx-yuan", "c1", 1, true, fxYuan, srcMap(EXT("ext:cny-week", "Курс юаня за неделю", "[Издание]", 1)), "Финансовый директор: валютная позиция и закупки"),
  envelope("card-subsidies", "c1", 2, true, subsidies, srcMap(EXT("ext:gov-subsidy", "Новые условия субсидирования инвестпроектов", "[Официальный источник]", 2)), "Генеральный директор: стратегия и инвестпроекты"),
  envelope("card-rail", "c1", 3, false, rail, srcMap(EXT("ext:rail-tariffs", "Повышение железнодорожных тарифов", "[Издание]", 3)), "Финансовый директор: логистические расходы"),
  envelope("card-consumption", "c1", 5, false, consumption, srcMap(EXT("ext:stat-consumption", "Макростатистика: потребление", "[Статистика]", 5), THESES["T-CONS-01"]), "Генеральный директор: спрос и продажи"),
  envelope("card-labor", "c1", 6, false, labor, srcMap(THESES["T-LAB-01"]), "Финансовый директор: расходы на персонал"),
  envelope("card-rate-treasurer", "c2", 0, true, rateTreasurer, RATE_SOURCES, "Руководитель казначейства: ликвидность, ставки, курсы валют"),
];

/** Какие карточки видит каждая компания (демо: у компаний разные ленты) */
export const MOCK_FEED_BY_COMPANY: Record<string, string[]> = {
  c1: ["card-rate-cfo", "card-fx-yuan", "card-subsidies", "card-rail", "card-consumption", "card-labor"],
  c2: ["card-rate-treasurer", "card-rail", "card-fx-yuan"],
  c3: ["card-consumption", "card-fx-yuan", "card-rate-treasurer"],
  c4: ["card-subsidies", "card-labor", "card-rate-cfo"],
};

/** Карточка отклонена критиком: пользователю не показывается, видна в режиме жюри */
export const MOCK_REJECTED = [
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
