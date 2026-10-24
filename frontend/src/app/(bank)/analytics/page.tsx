"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@alfalab/core-components/button";
import { FeedCard } from "@/components/feed/FeedCard";
import { Icon } from "@/components/ui/Icon";
import { Select } from "@/components/ui/Select";
import { ErrorState, StateBlock } from "@/components/states/StateBlock";
import { DISCLAIMER_ALWAYS, FACTOR_LABEL, FEED_FACTOR_FILTERS, MATERIALITY_LABEL, roleName } from "@/lib/labels";
import { plural } from "@/lib/format";
import { useFeed } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import type { FactorCode, Materiality } from "@/lib/types";

type ImpactFilter = Materiality | "all";
const IMPACTS: ImpactFilter[] = ["all", "high", "medium", "low"];
const FACTOR_OPTIONS: { value: FactorCode | "all"; label: string }[] = [
  { value: "all", label: "Все факторы" },
  ...FEED_FACTOR_FILTERS.map((f) => ({ value: f, label: FACTOR_LABEL[f] })),
];

/** Лента инсайтов: события, подобранные для компании и роли, с фильтрами по влиянию и фактору */
export default function AnalyticsPage() {
  const { company, role, hidden, setHidden, toast } = useSession();
  const { state, loading, reload } = useFeed();
  const [impact, setImpact] = useState<ImpactFilter>("all");
  const [factor, setFactor] = useState<FactorCode | "all">("all");

  const items = useMemo(() => {
    if (state.status !== "ready") return [];
    return state.data.filter(
      (i) => (impact === "all" || i.materiality === impact) && (factor === "all" || i.factor === factor),
    );
  }, [state, impact, factor]);

  const visibleCount = items.filter((i) => !hidden[i.id]).length;
  const hiddenCount = Object.keys(hidden).length;
  const filtered = impact !== "all" || factor !== "all";
  const reset = () => {
    setImpact("all");
    setFactor("all");
  };

  function hide(id: string, how: "hide" | "irrelevant") {
    setHidden(id, how);
    toast(how === "irrelevant" ? "Отметили как нерелевантное" : "Карточка скрыта", {
      label: "Отменить",
      run: () => setHidden(id, null),
    });
  }

  return (
    <>
      <nav className="crumbs -mb-2" aria-label="Навигация">
        <Link href="/" className="crumb">
          Главная
        </Link>
        <span className="muted" aria-hidden="true">/</span>
        <span>Аналитика для бизнеса</span>
      </nav>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 mb-1.5 text-[32px] leading-10 font-bold">Аналитика для бизнеса</h1>
          <p className="muted m-0 text-[15px] leading-[22px]">
            События, подобранные для {company?.name} и роли «{roleName(role)}»
          </p>
        </div>
        <nav className="tabs" aria-label="Режим просмотра">
          <Link href="/analytics" className="tab" aria-current="page">
            Лента
          </Link>
          <Link href="/analytics/digest" className="tab">
            Дайджест
          </Link>
        </nav>
      </div>

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-3">
          <div
            className={`flex flex-wrap items-center justify-between gap-2 ${state.status === "error" ? "hidden" : ""}`}
          >
            <div role="group" aria-label="Фильтры" className="flex flex-wrap items-center gap-2">
              <span className="muted mr-0.5 text-[14px]">Влияние</span>
              {IMPACTS.map((v) => (
                <button key={v} type="button" className="ft" aria-pressed={impact === v} onClick={() => setImpact(v)}>
                  {v === "all" ? "Любое" : MATERIALITY_LABEL[v]}
                </button>
              ))}
              <Select className="ml-1" variant="pill" label="Фактор" value={factor} options={FACTOR_OPTIONS} onChange={setFactor} />
              {filtered ? (
                <button type="button" className="lnk" onClick={reset}>
                  Сбросить
                </button>
              ) : null}
            </div>
            <span className="muted text-[14px]">
              {visibleCount} {plural(visibleCount, ["событие", "события", "событий"])}
            </span>
          </div>

          {loading ? (
            <div className="flex flex-col gap-3" aria-hidden="true">
              <div className="skeleton h-[188px] !rounded-[20px]" />
              <div className="skeleton h-[188px] !rounded-[20px]" />
              <div className="skeleton h-[188px] !rounded-[20px]" />
            </div>
          ) : state.status === "error" ? (
            <ErrorState error={state.error} onRetry={reload} />
          ) : state.status === "ready" && state.data.length === 0 ? (
            <StateBlock
              icon="bell"
              title={`Пока нет событий для ${company?.name ?? "компании"}`}
              text="Покажем их, когда найдём что-то важное для вашей отрасли и роли"
            />
          ) : items.length === 0 ? (
            <div className="plate px-6 py-12 text-center">
              <p className="m-0 mb-2 text-[18px] font-bold">По этим фильтрам событий нет</p>
              <p className="muted m-0 mb-5">Выберите другой уровень влияния или фактор</p>
              <Button view="secondary" size={40} onClick={reset}>
                Сбросить фильтры
              </Button>
            </div>
          ) : (
            items.map((it) =>
              hidden[it.id] ? (
                <div key={it.id} className="gone" role="status">
                  <span>
                    {hidden[it.id] === "irrelevant"
                      ? "Отметили как нерелевантное. Будем реже показывать похожие события."
                      : "Событие скрыто из ленты."}
                  </span>
                  <button type="button" className="lnk" onClick={() => setHidden(it.id, null)}>
                    Вернуть
                  </button>
                </div>
              ) : (
                <FeedCard
                  key={it.id}
                  item={it}
                  onHide={() => hide(it.id, "hide")}
                  onIrrelevant={() => hide(it.id, "irrelevant")}
                />
              ),
            )
          )}
          {hiddenCount > 0 && !loading ? (
            <p className="muted m-0 px-2 text-[14px]">Скрытых событий: {hiddenCount}</p>
          ) : null}
        </div>

        <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-4">
          <section className="plate flex flex-col gap-3.5">
            <h2 className="m-0 text-[18px] leading-6 font-bold">Как мы подбираем события</h2>
            <p className="muted m-0 text-[14px] leading-5">
              Сопоставляем новости и аналитику банка с признаками компании
            </p>
            <div className="flex flex-wrap gap-1.5">
              {company ? <span className="chip">{company.activity}</span> : null}
              {state.status === "ready"
                ? [...new Set(state.data.map((i) => FACTOR_LABEL[i.factor]))].map((f) => (
                    <span key={f} className="chip">
                      {f}
                    </span>
                  ))
                : null}
            </div>
          </section>
          <Link href="/analytics/analyze" className="plate flex items-start gap-3.5 transition-shadow hover:shadow-[var(--shadow-pop)]">
            <span className="av">
              <Icon name="doc" />
            </span>
            <span>
              <span className="block text-[16px] font-bold">Разобрать свою новость</span>
              <span className="muted mt-1 block text-[14px] leading-5">
                Вставьте текст или ссылку, покажем, как это касается компании
              </span>
            </span>
          </Link>
          <p className="muted m-0 px-2 text-[13px] leading-[18px]">{DISCLAIMER_ALWAYS}</p>
        </aside>
      </div>
    </>
  );
}
