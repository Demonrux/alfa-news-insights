"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ContactDialog } from "@/components/dialogs/ContactDialog";
import { ErrorState, StateBlock } from "@/components/states/StateBlock";
import { ClaimBox, ClaimLabel, ImpactLevel } from "@/components/ui/badges";
import { Icon } from "@/components/ui/Icon";
import { DISCLAIMER_ALWAYS, FACTOR_LABEL, OVERALL_IMPACT_LABEL, roleName } from "@/lib/labels";
import { plural } from "@/lib/format";
import { useFeed } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import type { FeedItem } from "@/lib/types";

type Period = "week" | "month";

const PERIODS: Record<Period, { label: string; title: string; days: number }> = {
  week: { label: "Неделя", title: "неделю", days: 7 },
  month: { label: "Месяц", title: "месяц", days: 31 },
};
const DAY = 24 * 60 * 60 * 1000;
const MATERIALITY_RANK = { high: 3, medium: 2, low: 1 } as const;

const shortDate = (d: Date) => d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });

/** События, сгруппированные по фактору, в порядке первого появления */
function groupByFactor(items: FeedItem[]) {
  const groups = new Map<string, FeedItem[]>();
  for (const it of items) {
    const name = FACTOR_LABEL[it.factor];
    groups.set(name, [...(groups.get(name) ?? []), it]);
  }
  return [...groups];
}

/**
 * Дайджест за период. Структура повторяет prompts/schemas/digest.json (summary, top, watch).
 * Пока бэкенда нет, сводка собирается из ленты: тексты берём из заголовков карточек, ничего не придумываем.
 */
export default function DigestPage() {
  const { company, role, toast } = useSession();
  const { state, loading, reload } = useFeed();
  const [period, setPeriod] = useState<Period>("week");
  const [mail, setMail] = useState(true);
  const [contact, setContact] = useState(false);
  const [now] = useState(() => new Date());

  const { title, days } = PERIODS[period];
  const from = new Date(now.getTime() - days * DAY);

  const items = useMemo(() => {
    if (state.status !== "ready") return [];
    return state.data.filter((i) => now.getTime() - new Date(i.createdAt).getTime() <= days * DAY);
  }, [state, days, now]);

  const top = useMemo(
    () => [...items].sort((a, b) => MATERIALITY_RANK[b.materiality] - MATERIALITY_RANK[a.materiality]).slice(0, 3),
    [items],
  );
  const groups = useMemo(() => groupByFactor(items), [items]);
  const high = items.filter((i) => i.materiality === "high").length;
  const count = (t: FeedItem["overallImpact"]) => items.filter((i) => i.overallImpact === t).length;
  const range = `${shortDate(from)} — ${shortDate(now)}`;
  const eventTitle = `Дайджест за ${title}, ${range}`;

  function toggleMail(on: boolean) {
    setMail(on);
    toast(on ? "Будем присылать дайджест по понедельникам" : "Рассылка отключена");
  }

  return (
    <>
      <nav className="crumbs -mb-2" aria-label="Навигация">
        <Link href="/" className="crumb">Главная</Link>
        <span className="muted" aria-hidden="true">/</span>
        <Link href="/analytics" className="crumb">Аналитика для бизнеса</Link>
        <span className="muted" aria-hidden="true">/</span>
        <span>Дайджест</span>
      </nav>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 mb-1.5 text-[32px] leading-10 font-bold">Дайджест за {title}</h1>
          <p className="muted m-0 text-[15px] leading-[22px]">
            {range} · {company?.name} · для роли «{roleName(role)}»
          </p>
        </div>
        <nav className="tabs" aria-label="Режим просмотра">
          <Link href="/analytics" className="tab">Лента</Link>
          <Link href="/analytics/digest" className="tab" aria-current="page">Дайджест</Link>
        </nav>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="seg" role="group" aria-label="Период">
          {(Object.keys(PERIODS) as Period[]).map((p) => (
            <button key={p} type="button" className="sg" aria-pressed={period === p} onClick={() => setPeriod(p)}>
              {PERIODS[p].label}
            </button>
          ))}
        </div>
        <span className="flex-1" />
        <label className="toggle">
          <input type="checkbox" checked={mail} onChange={(e) => toggleMail(e.target.checked)} />
          Присылать на почту по понедельникам
        </label>
        <button type="button" className="btn btn-outline" onClick={() => window.print()}>
          <Icon name="download" size={18} />
          Скачать PDF
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-3" aria-hidden="true">
          <div className="skeleton h-40 !rounded-[20px]" />
          <div className="skeleton h-64 !rounded-[20px]" />
        </div>
      ) : state.status === "error" ? (
        <ErrorState error={state.error} onRetry={reload} />
      ) : items.length === 0 ? (
        <StateBlock
          icon="bell"
          title={`За ${title} событий нет`}
          text="Выберите другой период или вернитесь в ленту"
        />
      ) : (
        <>
          <section className="plate flex flex-col gap-4" aria-labelledby="d-main">
            <h2 id="d-main" className="h2">Главное</h2>
            <ClaimBox type="ai" className="flex flex-col gap-3">
              <ClaimLabel type="ai" />
              <ol className="m-0 flex flex-col gap-2.5 pl-[22px] text-[16px] leading-6">
                {top.map((e) => (
                  <li key={e.id}>
                    <Link href={`/analytics/${e.id}`} className="font-bold hover:underline">
                      {e.headline}
                    </Link>
                  </li>
                ))}
              </ol>
            </ClaimBox>
          </section>

          <p className="m-0 text-[15px] leading-[22px] text-ink-2">
            {items.length} {plural(items.length, ["событие", "события", "событий"])}: {count("negative")}{" "}
            {plural(count("negative"), ["риск", "риска", "рисков"])}, {count("positive")}{" "}
            {plural(count("positive"), ["возможность", "возможности", "возможностей"])}, {count("mixed")} смешанных.
            С высоким влиянием — {high}.
          </p>

          <section className="plate flex flex-col gap-1" aria-labelledby="d-events">
            <h2 id="d-events" className="h2">События за {title}</h2>
            {groups.map(([name, rows]) => (
              <div key={name}>
                <h3 className="grp">{name}</h3>
                {rows.map((e) => (
                  <Link key={e.id} href={`/analytics/${e.id}`} className="drow">
                    <span className="rt font-semibold">{e.headline}</span>
                    <span className={`dtype dtype--${e.overallImpact}`}>{OVERALL_IMPACT_LABEL[e.overallImpact]}</span>
                    <ImpactLevel level={e.materiality} short />
                  </Link>
                ))}
              </div>
            ))}
          </section>

          <section className="plate flex flex-col gap-3.5" aria-labelledby="d-q">
            <h2 id="d-q" className="h2">Что обсудить с командой</h2>
            <ClaimBox type="hypothesis" className="flex flex-col gap-3">
              <ClaimLabel type="hypothesis" />
              <ul className="m-0 flex flex-col gap-2 pl-5 text-[16px] leading-6">
                {top.slice(0, 2).map((e) => (
                  <li key={e.id}>Как «{FACTOR_LABEL[e.factor].toLowerCase()}» отразится на планах команды на ближайший квартал</li>
                ))}
              </ul>
            </ClaimBox>
            <button
              type="button"
              className="btn btn-sec self-start"
              aria-haspopup="dialog"
              onClick={() => setContact(true)}
            >
              Связаться с менеджером
            </button>
          </section>
        </>
      )}

      <p className="muted m-0 text-[13px]">{DISCLAIMER_ALWAYS}</p>

      {contact ? (
        <ContactDialog kind="contact_manager" cardId={null} eventTitle={eventTitle} onClose={() => setContact(false)} />
      ) : null}
    </>
  );
}
