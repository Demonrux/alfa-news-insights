"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@alfalab/core-components/button";
import { ContactDialog } from "@/components/dialogs/ContactDialog";
import { ClaimBox, ClaimLabel, ImpactLevel, TypeBadge } from "@/components/ui/badges";
import { Icon } from "@/components/ui/Icon";
import { sendFeedback } from "@/lib/api";
import {
  ACTION_TYPE_LABEL,
  BADGE_EXTERNAL,
  CLAIM_HINT,
  CLAIM_LABEL,
  CONFIDENCE_LABEL,
  CTA_LABEL,
  DISCLAIMER_ALWAYS,
  DISCLAIMER_BY_BASIS,
  FACTOR_LABEL,
  FEATURE_LABEL,
  LIKELIHOOD_LABEL,
  SOURCE_KIND_LABEL,
  roleName,
} from "@/lib/labels";
import { formatDate, formatRelative, isStale } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Action, CardEnvelope, FeedbackKind } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { DerivationPanel } from "./DerivationPanel";
import { collectSources, sourcesFor } from "./sources";

const FEEDBACK: { kind: FeedbackKind | "hide"; label: string; reply: string }[] = [
  { kind: "useful", label: "Полезно", reply: "Учтём при подборе событий" },
  { kind: "not_important", label: "Не важно", reply: "Будем реже показывать похожее" },
  { kind: "error", label: "Ошибка", reply: "Передали на проверку аналитикам" },
  { kind: "hide", label: "Скрыть", reply: "" },
];

const STATUS_LABEL = { confirmed: "", reported: "Сообщается", speculative: "Предположение" } as const;

function featureLabel(code: string): string {
  return FEATURE_LABEL[code.replace("feature:", "")] ?? "Признак компании";
}

/** Карточка инсайта: блоки идут по шести вопросам кейса, типы утверждений различаются рамкой, иконкой и подписью */
export function InsightView({ env }: { env: CardEnvelope }) {
  const { card } = env;
  const router = useRouter();
  const { company, setHidden, toast } = useSession();
  const [contact, setContact] = useState<Action | null>(null);
  const [derivation, setDerivation] = useState(false);
  const [chat, setChat] = useState<{ open: boolean; seed: string | null }>({ open: false, seed: null });
  const [feedback, setFeedback] = useState<FeedbackKind | null>(null);

  const lead = card.ai_conclusions[0];
  const restConclusions = card.ai_conclusions.slice(1);
  const sources = collectSources(env);
  const factsSources = sourcesFor(env, card.what_happened.flatMap((w) => w.source_ids));
  const external = card.source_basis === "external_only";
  const disclaimer = card.disclaimer ?? `${DISCLAIMER_ALWAYS} ${DISCLAIMER_BY_BASIS[card.source_basis]}`;
  const features = [...new Set(card.why_relevant.map((w) => w.feature))];

  async function pick(kind: (typeof FEEDBACK)[number]) {
    if (kind.kind === "hide") {
      setHidden(env.id, "hide");
      toast("Карточка скрыта", { label: "Отменить", run: () => setHidden(env.id, null) });
      router.push("/analytics");
      return;
    }
    const next = feedback === kind.kind ? null : kind.kind;
    setFeedback(next);
    if (next) await sendFeedback(env.id, next);
  }

  return (
    <>
      <nav className="crumbs" aria-label="Навигация">
        <Link href="/" className="crumb">
          Главная
        </Link>
        <span className="muted" aria-hidden="true">/</span>
        <Link href="/analytics" className="crumb">
          Аналитика для бизнеса
        </Link>
        <span className="muted" aria-hidden="true">/</span>
        <span>{FACTOR_LABEL[env.primaryFactor]}</span>
      </nav>

      <div className="flex flex-wrap items-start gap-6">
        <article className="sheet min-w-0 flex-[999_1_560px]">
          <header className="flex flex-col gap-[18px] px-10 pt-9 pb-8 max-[760px]:px-5 max-[760px]:pt-6">
            <div className="flex flex-wrap items-center gap-3.5">
              <TypeBadge type={card.overall_impact} large />
              <ImpactLevel level={card.materiality} strong />
              <span className="muted text-[14px]">{formatRelative(env.createdAt)}</span>
              {external ? <span className="tag-ext">{card.badge ?? BADGE_EXTERNAL}</span> : null}
              <span className="flex-1" />
              <div className="group relative inline-flex">
                <button
                  type="button"
                  aria-describedby="legend"
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[14px] text-ink-2 hover:bg-field"
                >
                  <Icon name="info" size={16} />
                  Как читать карточку
                </button>
                <div
                  id="legend"
                  role="tooltip"
                  className="invisible absolute top-[38px] right-0 z-10 flex w-80 flex-col gap-2.5 rounded-[14px] bg-white p-4 opacity-0 shadow-[0_8px_24px_rgba(0,0,0,.16)] group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
                >
                  {(["fact", "bank", "ai", "hypothesis"] as const).map((t) => (
                    <div key={t} className="flex items-center gap-2.5 text-[14px] leading-5">
                      <span
                        className={`h-[18px] w-7 flex-none rounded-[5px] ${
                          t === "fact"
                            ? "border border-line"
                            : t === "bank"
                              ? "border-2 border-accent"
                              : t === "ai"
                                ? "border-[1.5px] border-dashed border-[#2a77ef] bg-[#f5f9ff]"
                                : "border-[3px] border-double border-[#c98a3a] bg-[#fffaf2]"
                        }`}
                      />
                      {CLAIM_LABEL[t]}. {CLAIM_HINT[t]}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <h1 className="m-0 max-w-[34ch] text-[32px] leading-10 font-bold tracking-[-0.3px] max-[760px]:text-[24px] max-[760px]:leading-[30px]">
              {card.headline}
            </h1>

            {lead ? (
              <ClaimBox type="ai" className="!gap-1.5 !px-[18px] !py-3.5">
                <ClaimLabel type="ai" />
                <p className="m-0 max-w-[64ch] text-[17px] leading-[26px] font-medium">{lead.text}</p>
              </ClaimBox>
            ) : null}

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[14px] text-ink-2">
              <span>Фактор: {FACTOR_LABEL[env.primaryFactor].toLowerCase()}</span>
              {env.criticPassed ? (
                <button
                  type="button"
                  className="inline-flex min-h-6 items-center gap-1.5 font-semibold text-[#1d5bbf] hover:underline"
                  onClick={() => setDerivation(true)}
                >
                  <Icon name="shield" size={16} />
                  Проверено критиком
                </button>
              ) : null}
              <span>Вывод для роли «{roleName(card.role)}»</span>
            </div>
          </header>

          <section className="sec" aria-labelledby="s-what">
            <h2 id="s-what" className="h2">
              Что произошло
            </h2>
            <ClaimBox type="fact">
              <ClaimLabel type="fact" />
              <ul className="ul">
                {card.what_happened.map((w) => (
                  <li key={w.text}>
                    <span>
                      {w.text}
                      {STATUS_LABEL[w.status] ? (
                        <span className="muted ml-2 text-[13px]">({STATUS_LABEL[w.status]})</span>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
              {factsSources.length ? (
                <span className="muted text-[14px]">
                  {factsSources.map((s) => `${s.outlet ?? SOURCE_KIND_LABEL[s.kind]}${s.date ? `, ${formatDate(s.date)}` : ""}`).join(" · ")}
                </span>
              ) : null}
            </ClaimBox>
          </section>

          <section className="sec" aria-labelledby="s-why">
            <h2 id="s-why" className="h2">
              Почему это важно именно вам
            </h2>
            <p className="muted m-0 text-[15px]">
              Вывод основан на признаках компании ({features.length})
            </p>
            <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
              {card.why_relevant.map((w) => (
                <li key={w.feature + w.factor} className="flex flex-col gap-1">
                  <span className="sign self-start">
                    <Icon name="growth" size={16} />
                    {featureLabel(w.feature)}
                  </span>
                  <span className="muted pl-3 text-[14px] leading-5">{w.explanation}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="sec" aria-labelledby="s-bank">
            <h2 id="s-bank" className="h2">
              Позиция Альфа-Банка
            </h2>
            {card.bank_view.length > 0 ? (
              <ClaimBox type="bank">
                {card.bank_view.map((b) => (
                  <div key={b.thesis_id} className="flex flex-col gap-1.5">
                    <ClaimLabel type="bank" title={`Отчёт «${b.report}»`} sub={`, ${formatDate(b.report_date)}`} />
                    <p className="p">{b.text}</p>
                    {isStale(b.report_date) ? (
                      <div className="flex items-start gap-2.5 rounded-[10px] bg-[#ffefd9] px-3 py-2.5 text-[14px] leading-5 text-[#8a4a00]">
                        <Icon name="clock" size={20} />
                        <span>
                          <b>Позиция от {formatDate(b.report_date)}, могла устареть.</b> Проверим актуальность при следующем обновлении отчёта.
                        </span>
                      </div>
                    ) : null}
                  </div>
                ))}
              </ClaimBox>
            ) : (
              <div className="flex items-start gap-3 rounded-xl border border-dashed border-[#babbc2] p-4 text-[15px] leading-[22px] text-ink-2">
                <Icon name="info" />
                <span>Банк не публиковал позицию по этой теме. Карточка построена только на внешних источниках.</span>
              </div>
            )}
          </section>

          {restConclusions.length > 0 ? (
            <section className="sec" aria-labelledby="s-ai">
              <h2 id="s-ai" className="h2">
                Ещё выводы для вас
              </h2>
              <ClaimBox type="ai">
                <ClaimLabel type="ai" />
                <ul className="m-0 flex list-none flex-col gap-3 p-0">
                  {restConclusions.map((c) => (
                    <li key={c.text} className="flex flex-col gap-1">
                      <span className="text-[16px] leading-6">{c.text}</span>
                      <span className="muted text-[13px]">{CONFIDENCE_LABEL[c.confidence]}</span>
                    </li>
                  ))}
                </ul>
              </ClaimBox>
            </section>
          ) : null}

          <section className="sec" aria-labelledby="s-imp">
            <h2 id="s-imp" className="h2">
              Влияние
            </h2>
            <div className="flex flex-wrap items-center gap-5">
              <ImpactLevel level={card.materiality} short strong />
              <p className="p flex-[1_1_320px]">{card.impact.criterion}</p>
            </div>
            {card.impact.estimate ? (
              <ClaimBox type="ai" className="!gap-1.5">
                <ClaimLabel type="ai" title={CLAIM_LABEL.estimate} />
                <span className="muted text-[13px]">{card.impact.estimate.metric}</span>
                <span className="text-[20px] leading-[26px] font-bold">{card.impact.estimate.range}</span>
                <span className="muted text-[13px]">
                  {card.impact.estimate.method} · {CONFIDENCE_LABEL[card.impact.estimate.confidence]}
                </span>
              </ClaimBox>
            ) : card.impact.no_estimate_reason ? (
              <p className="muted m-0 text-[13px] leading-[18px]">{card.impact.no_estimate_reason}</p>
            ) : null}
          </section>

          {card.risks.length > 0 || card.opportunities.length > 0 ? (
            <section className="sec" aria-labelledby="s-ro">
              <h2 id="s-ro" className="h2">
                Риски и возможности
              </h2>
              <ClaimBox type="ai">
                <ClaimLabel type="ai" />
                <div className="mt-1.5 grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
                  {[
                    { title: "Риски", items: card.risks },
                    { title: "Возможности", items: card.opportunities },
                  ]
                    .filter((g) => g.items.length)
                    .map((g) => (
                      <div key={g.title}>
                        <h3 className="m-0 mb-1 text-[16px] leading-[22px] font-bold">{g.title}</h3>
                        {g.items.map((it) => (
                          <div key={it.text} className="flex flex-col gap-1.5 border-t border-[#dbe3ef] py-2.5 text-[15px] leading-[22px]">
                            {it.text}
                            <span className="muted text-[13px]">{CONFIDENCE_LABEL[it.confidence]}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                </div>
              </ClaimBox>
            </section>
          ) : null}

          {card.hypotheses.length > 0 ? (
            <section className="sec" aria-labelledby="s-hyp">
              <h2 id="s-hyp" className="h2">
                Гипотезы
              </h2>
              <ClaimBox type="hypothesis">
                <ClaimLabel type="hypothesis" />
                <ul className="m-0 flex list-none flex-col gap-3 p-0">
                  {card.hypotheses.map((h) => (
                    <li key={h.text} className="flex flex-col gap-1">
                      <span className="text-[16px] leading-6">{h.text}</span>
                      <span className="muted text-[14px]">Как проверить: {h.how_to_check}</span>
                    </li>
                  ))}
                </ul>
              </ClaimBox>
            </section>
          ) : null}

          <section className="sec" aria-labelledby="s-do">
            <h2 id="s-do" className="h2">
              Что можно сделать
            </h2>
            <div className="flex flex-col gap-3">
              {card.actions.map((a) => (
                <div key={a.text} className={a.cta ? "act" : "px-6"}>
                  <div className={`flex flex-col gap-1.5 ${a.cta ? "flex-[1_1_320px]" : ""}`}>
                    {a.type !== "bank_product" ? (
                      <span className="muted text-[13px] font-semibold">{ACTION_TYPE_LABEL[a.type]}</span>
                    ) : null}
                    <span className="text-[16px] leading-6">{a.text}</span>
                    {a.product ? (
                      <span className="text-[14px] leading-5 text-ink-2">
                        Продукт банка: <b className="text-ink">{a.product}</b>
                      </span>
                    ) : null}
                  </div>
                  {a.cta ? (
                    <Button view="primary" size={48} onClick={() => setContact(a)} aria-haspopup="dialog">
                      {CTA_LABEL[a.cta]}
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
          </section>

          {card.scenarios.length > 0 ? (
            <details className="fold">
              <summary>
                Сценарии
                <Icon name="chevronDown" className="chev" />
              </summary>
              <div className="dbody">
                <ClaimBox type="hypothesis">
                  <ClaimLabel type="hypothesis" />
                  {card.scenarios.map((s) => (
                    <div key={s.name} className="grid gap-4 border-t border-[#f0dcc0] py-3 text-[15px] leading-[22px] [grid-template-columns:140px_minmax(0,1fr)] max-[760px]:grid-cols-1 max-[760px]:gap-1">
                      <span className="flex flex-col gap-0.5 font-bold">
                        {s.name.charAt(0).toUpperCase() + s.name.slice(1)}
                        <span className="text-[13px] font-normal text-ink-2">{LIKELIHOOD_LABEL[s.likelihood]}</span>
                      </span>
                      <span className="flex flex-col gap-1">
                        {s.text}
                        <span className="muted text-[14px]">Что должно произойти: {s.trigger}</span>
                        <span className="muted text-[14px]">Почему так: {s.logic}</span>
                      </span>
                    </div>
                  ))}
                </ClaimBox>
              </div>
            </details>
          ) : null}

          {card.open_questions.length > 0 ? (
            <section className="sec" aria-labelledby="s-q">
              <h2 id="s-q" className="h2">
                Что стоит уточнить
              </h2>
              <div className="flex flex-wrap gap-2">
                {card.open_questions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="ft !h-auto !whitespace-normal !py-2 text-left"
                    onClick={() => setChat({ open: true, seed: q })}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          <details id="sources" className="fold">
            <summary>
              Источники
              <span className="inline-flex items-center gap-3">
                <span className="muted text-[15px] font-normal">{sources.length}</span>
                <Icon name="chevronDown" className="chev" />
              </span>
            </summary>
            <div className="dbody !gap-0">
              {sources.map((s) => (
                <a key={s.id} href={s.url ?? "#"} className="src" onClick={(e) => !s.url && e.preventDefault()}>
                  <span className="kind">{SOURCE_KIND_LABEL[s.kind]}</span>
                  <span className="flex-1">
                    <span className="st font-semibold">
                      {s.outlet ? `${s.outlet}: ` : ""}
                      {s.title}
                    </span>
                    {s.date ? <span className="muted">, {formatDate(s.date)}</span> : null}
                  </span>
                  <Icon name="external" size={16} />
                </a>
              ))}
            </div>
          </details>

          <footer className="flex flex-col gap-4 border-t border-line-2 px-10 pt-6 pb-7 max-[760px]:px-5">
            <span className="text-[16px] font-bold">Насколько это полезно?</span>
            <div className="flex flex-wrap items-center gap-2">
              {FEEDBACK.map((f) => (
                <button
                  key={f.kind}
                  type="button"
                  className={`fb ${feedback === f.kind ? "on" : ""}`}
                  aria-pressed={f.kind !== "hide" ? feedback === f.kind : undefined}
                  onClick={() => pick(f)}
                >
                  {f.label}
                </button>
              ))}
              {feedback ? (
                <span role="status" className="muted ml-2 text-[14px]">
                  {FEEDBACK.find((f) => f.kind === feedback)?.reply}
                </span>
              ) : null}
            </div>
            <p className="muted m-0 text-[13px] leading-[18px]">{disclaimer}</p>
          </footer>
        </article>

        <aside className="sticky top-6 flex min-w-0 flex-[1_1_300px] flex-col gap-3">
          <button type="button" className="side-card" onClick={() => setDerivation(true)}>
            <span className="av !bg-[#e4f0ff] !text-[#1d5bbf]">
              <Icon name="shield" />
            </span>
            <span>
              <span className="block text-[16px] font-bold">Как получен вывод</span>
              <span className="muted mt-1 block text-[14px] leading-5">
                {sources.length} {sources.length === 1 ? "источник" : "источника"}
                {env.criticPassed ? ", прошёл проверку критиком" : ""}
              </span>
            </span>
          </button>
          <button type="button" className="side-card" onClick={() => setChat({ open: true, seed: null })}>
            <span className="av">
              <Icon name="chat" />
            </span>
            <span>
              <span className="block text-[16px] font-bold">Уточнить</span>
              <span className="muted mt-1 block text-[14px] leading-5">Спросите про срок, другой разрез или роль</span>
            </span>
          </button>
          {company ? (
            <div className="side-card flex-col gap-2.5">
              <span className="font-bold">Компания</span>
              <span className="text-[14px] leading-5">{company.name}, {company.label.split(" · ")[0].toLowerCase()}</span>
            </div>
          ) : null}
        </aside>
      </div>

      {contact && contact.cta ? (
        <ContactDialog
          kind={contact.cta}
          cardId={env.id}
          eventTitle={card.headline}
          product={contact.product}
          onClose={() => setContact(null)}
        />
      ) : null}
      {derivation ? <DerivationPanel env={env} onClose={() => setDerivation(false)} /> : null}
      {chat.open ? <ChatPanel env={env} seed={chat.seed} onClose={() => setChat({ open: false, seed: null })} /> : null}
    </>
  );
}
