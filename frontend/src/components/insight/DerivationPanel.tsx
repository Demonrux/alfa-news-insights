"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { getRejected } from "@/lib/api";
import { FEATURE_LABEL, SOURCE_KIND_LABEL } from "@/lib/labels";
import { formatDate } from "@/lib/format";
import { collectSources } from "./sources";
import type { CardEnvelope } from "@/lib/types";

type Rejected = Awaited<ReturnType<typeof getRejected>>;

/** Режим жюри включается адресом ?jury=1 и показывает карточки, не прошедшие критика */
function isJury(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("jury") === "1";
}

/** «Как получен вывод»: шаги агента, источники, признаки компании и замечания критика */
export function DerivationPanel({ env, onClose }: { env: CardEnvelope; onClose: () => void }) {
  const [tab, setTab] = useState<"card" | "jury">("card");
  const [rejected, setRejected] = useState<Rejected>([]);
  const jury = isJury();
  const sources = collectSources(env);

  useEffect(() => {
    if (jury) getRejected().then(setRejected);
  }, [jury]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const features = env.card.why_relevant;
  const bankCount = sources.filter((s) => s.kind === "bank_report").length;

  return (
    <>
      <button type="button" className="panel-back" aria-label="Закрыть панель" onClick={onClose} />
      <aside className="panel" role="dialog" aria-modal="true" aria-labelledby="dp-title">
        <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4">
          <div>
            <h2 id="dp-title" className="m-0 mb-1.5 text-[24px] leading-8 font-bold">
              Как получен вывод
            </h2>
            <p className="muted m-0 text-[14px] leading-5">Шаги агента, источники и признаки компании</p>
          </div>
          <button type="button" className="btn-icon" aria-label="Закрыть" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-6 pb-6">
          {jury ? (
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="inline-flex gap-0.5 rounded-[10px] bg-field p-[3px]" role="group" aria-label="Что показать">
                {(
                  [
                    ["card", "Эта карточка"],
                    ["jury", "Отклонённые критиком"],
                  ] as const
                ).map(([k, l]) => (
                  <button
                    key={k}
                    type="button"
                    aria-pressed={tab === k}
                    onClick={() => setTab(k)}
                    className={`h-[34px] rounded-lg px-3 text-[14px] font-semibold ${tab === k ? "bg-white shadow-sm" : "text-ink-2"}`}
                  >
                    {l}
                  </button>
                ))}
              </div>
              <span className="inline-flex h-[26px] items-center gap-1.5 rounded-lg border border-dashed border-[#898991] px-2.5 text-[13px] text-ink-2">
                <Icon name="lock" size={16} />
                Режим жюри
              </span>
            </div>
          ) : null}

          {tab === "card" ? (
            <>
              <div className="flex flex-wrap items-center gap-3 rounded-[14px] bg-field px-4 py-3.5">
                {env.criticPassed ? (
                  <span className="inline-flex h-7 items-center gap-1.5 rounded-lg bg-[#e4f0ff] px-2.5 text-[13px] font-bold text-[#1d5bbf]">
                    <Icon name="shield" size={16} />
                    Проверено критиком
                  </span>
                ) : null}
                <span className="text-[14px]">
                  {sources.length} {sources.length === 1 ? "источник" : "источника"}
                  {bankCount ? `, из них отчётов банка: ${bankCount}` : ""}
                </span>
              </div>

              <ol className="m-0 flex list-none flex-col p-0">
                {(env.trace ?? []).map((s, i, arr) => (
                  <li key={s.title} className="grid grid-cols-[32px_minmax(0,1fr)] gap-3.5">
                    <div className="flex flex-col items-center">
                      <span className="grid size-8 place-items-center rounded-full bg-accent text-[14px] font-bold text-white">
                        {i === arr.length - 1 ? <Icon name="check" size={16} /> : i + 1}
                      </span>
                      {i < arr.length - 1 ? <span className="mx-auto mt-1 w-0.5 flex-1 bg-line" /> : null}
                    </div>
                    <div className="flex flex-col gap-1.5 pb-5">
                      <span className="text-[16px] leading-8 font-bold">{s.title}</span>
                      <span className="muted text-[14px] leading-5">{s.detail}</span>
                      {s.features?.length ? (
                        <div className="flex flex-wrap gap-1.5">
                          {s.features.map((f) => (
                            <span key={f} className="chip">
                              {f}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {s.note ? <div className="rounded-xl bg-[#f7f8f9] px-3.5 py-3 text-[14px] leading-5">{s.note}</div> : null}
                    </div>
                  </li>
                ))}
              </ol>

              <section className="flex flex-col gap-2.5">
                <h3 className="m-0 text-[18px] leading-6 font-bold">Источники</h3>
                {sources.map((s) => (
                  <a key={s.id} href={s.url ?? "#"} className="flex items-center gap-2.5 text-[14px]" onClick={(e) => !s.url && e.preventDefault()}>
                    <span
                      className={`inline-flex h-[22px] items-center rounded-md px-2 text-[12px] font-bold whitespace-nowrap ${
                        s.kind === "bank_report" ? "border-2 border-accent" : "border border-[#babbc2] text-ink-2"
                      }`}
                    >
                      {SOURCE_KIND_LABEL[s.kind]}
                    </span>
                    <span className="flex-1">
                      {s.title}
                      {s.date ? <span className="muted">, {formatDate(s.date)}</span> : null}
                    </span>
                    <Icon name="external" size={16} />
                  </a>
                ))}
              </section>

              <section className="flex flex-col gap-2.5">
                <h3 className="m-0 text-[18px] leading-6 font-bold">Признаки компании</h3>
                <table className="w-full border-collapse text-[14px] leading-5">
                  <thead>
                    <tr className="muted text-left text-[13px]">
                      <th className="border-b border-line-2 py-2 pr-2 font-semibold">Признак</th>
                      <th className="border-b border-line-2 py-2 pr-2 font-semibold">Как повлиял</th>
                    </tr>
                  </thead>
                  <tbody>
                    {features.map((f) => (
                      <tr key={f.feature + f.factor}>
                        <td className="border-b border-[#f2f3f5] py-2.5 pr-2 align-top">
                          {FEATURE_LABEL[f.feature.replace("feature:", "")] ?? "Признак компании"}
                        </td>
                        <td className="muted border-b border-[#f2f3f5] py-2.5 align-top">{f.explanation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="rounded-xl bg-field px-3.5 py-3 text-[14px] leading-5">
                Эти карточки не прошли проверку и пользователю не показаны. Вкладка видна только в демо-режиме для жюри.
              </div>
              {rejected.map((r) => (
                <article key={r.id} className="flex flex-col gap-3 rounded-2xl border-[1.5px] border-dashed border-[#babbc2] p-[18px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex h-[26px] items-center gap-1.5 rounded-lg bg-[#ffebeb] px-2.5 text-[13px] font-bold text-[#a8150a]">
                      <Icon name="ban" size={16} />
                      Не прошла проверку
                    </span>
                    <span className="chip">{r.factor}</span>
                  </div>
                  <span className="text-[16px] leading-[22px] font-bold">{r.headline}</span>
                  <div className="flex flex-col gap-2 text-[14px] leading-5">
                    <span className="font-bold">Замечания критика</span>
                    {r.issues.map((x) => (
                      <span key={x}>· {x}</span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line-2 px-6 py-4">
          <span className="muted text-[13px]">Аналитика не является инвестиционной рекомендацией</span>
        </div>
      </aside>
    </>
  );
}
