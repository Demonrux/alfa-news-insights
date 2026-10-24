"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { TypeBadge } from "@/components/ui/badges";
import { DISCLAIMER_ALWAYS } from "@/lib/labels";
import { useFeed } from "@/lib/hooks";
import { useSession } from "@/lib/session";

const STEPS = ["Читаем новость", "Сверяем с аналитикой банка", "Сопоставляем с профилем компании", "Проверяем вывод"];
const STEP_MS = 1200;

type Phase = "idle" | "loading" | "done";

/** Разбор своей новости: пользователь вставляет текст или ссылку, получает обычную карточку инсайта */
export default function AnalyzePage() {
  const { company } = useSession();
  const { state } = useFeed();
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (phase !== "loading") return;
    const t = setInterval(() => setStep((s) => s + 1), STEP_MS);
    return () => clearInterval(t);
  }, [phase]);

  // Когда все шаги пройдены, разбор готов
  if (phase === "loading" && step >= STEPS.length) setPhase("done");

  // Пока нет бэкенда, вместо разбора открываем первую готовую карточку ленты
  const result = state.status === "ready" ? state.data[0] : undefined;
  const run = () => {
    setStep(0);
    setPhase("loading");
  };

  return (
    <div className="flex w-full max-w-[780px] flex-col gap-5">
      <nav className="crumbs" aria-label="Навигация">
        <Link href="/" className="crumb">Главная</Link>
        <span className="muted" aria-hidden="true">/</span>
        <Link href="/analytics" className="crumb">Аналитика для бизнеса</Link>
        <span className="muted" aria-hidden="true">/</span>
        <span>Разбор новости</span>
      </nav>

      <div>
        <h1 className="m-0 mb-1.5 text-[32px] leading-10 font-bold">Разбор своей новости</h1>
        <p className="muted m-0 text-[16px] leading-6">
          Вставьте текст или ссылку — покажем, как событие касается {company?.name ?? "вашей компании"}
        </p>
      </div>

      <section className="plate flex flex-col gap-4">
        <label className="ta">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Например, ссылка на новость или текст сообщения регулятора"
          />
          <span className="lb">Новость или ссылка</span>
        </label>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span className="muted text-[13px]">Только открытые источники</span>
          <button
            type="button"
            className="btn btn--m btn-primary"
            disabled={!text.trim() || phase === "loading"}
            onClick={run}
          >
            Получить разбор
          </button>
        </div>
      </section>

      {phase !== "idle" ? (
        <section className="plate flex flex-col gap-3" role="status" aria-live="polite">
          {STEPS.map((label, i) => {
            const done = phase === "done" || i < step;
            const active = phase === "loading" && i === step;
            return (
              <div key={label} className={`flex items-center gap-3 text-[15px] leading-[22px] ${done || active ? "" : "muted"}`}>
                {done ? (
                  <span className="grid size-5 place-items-center rounded-full bg-accent text-white">
                    <Icon name="check" size={12} />
                  </span>
                ) : active ? (
                  <span className="size-5 animate-spin rounded-full border-[2.5px] border-[#d2d3d9] border-t-accent" aria-hidden="true" />
                ) : (
                  <span className="size-5 rounded-full border-2 border-[#d2d3d9]" aria-hidden="true" />
                )}
                {label}
              </div>
            );
          })}
        </section>
      ) : null}

      {phase === "done" && result ? (
        <Link
          href={`/analytics/${result.id}`}
          className="plate flex flex-col gap-3 border-[1.5px] border-accent transition-shadow hover:shadow-[var(--shadow-pop)]"
        >
          <div className="flex items-center gap-2.5">
            <TypeBadge type={result.overallImpact} />
            <span className="muted text-[13px]">Готово, откроется как обычная карточка</span>
          </div>
          <span className="text-[20px] leading-[26px] font-bold">{result.headline}</span>
          <span className="text-[14px] font-bold">Открыть карточку</span>
        </Link>
      ) : null}

      <section className="flex flex-col gap-1 px-1">
        <h2 className="m-0 my-2 text-[18px] leading-6 font-bold">Недавние разборы</h2>
        <Link href="/analytics" className="hist">
          <span>Изменения в правилах валютного контроля</span>
          <span className="muted">Вчера</span>
        </Link>
      </section>
      <p className="muted m-0 px-1 text-[13px]">{DISCLAIMER_ALWAYS}</p>
    </div>
  );
}
