"use client";

import { useEffect, useRef, useState } from "react";
import { ClaimLabel } from "@/components/ui/badges";
import { Icon } from "@/components/ui/Icon";
import { CHAT_BASIS_LABEL } from "@/lib/labels";
import { useModal } from "@/lib/useModal";
import type { CardEnvelope } from "@/lib/types";

interface Message {
  id: number;
  from: "me" | "bot";
  text: string;
  basis?: string;
  pending?: boolean;
}

/**
 * Ответ чата по карточке. Формат повторяет prompts/schemas/chat.json (answer, followups, basis).
 * Пока бэкенда нет, ответ собирается из самой карточки, поэтому показываем основание честно.
 */
function mockReply(env: CardEnvelope, question: string): { answer: string; basis: string } {
  const q = question.toLowerCase();
  const c = env.card;
  if (/роль|казнач|финдир|гендир|собственник/.test(q)) {
    return {
      answer: "Акценты зависят от роли. Переключите роль в шапке, и выводы в карточке перестроятся под неё.",
      basis: "no_data",
    };
  }
  const lead = c.ai_conclusions[0]?.text ?? "";
  const bank = c.bank_view[0]?.text ? ` Позиция банка: ${c.bank_view[0].text}` : "";
  return {
    answer: `${lead}${bank}`.trim(),
    basis: c.bank_view.length ? c.source_basis : "external_only",
  };
}

/** Чат по карточке: уточняющие вопросы, у каждого ответа подпись основания */
export function ChatPanel({
  env,
  seed,
  onClose,
}: {
  env: CardEnvelope;
  seed: string | null;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);
  const seeded = useRef(false);
  const nextId = useRef(0);
  const timers = useRef<number[]>([]);
  useModal(panel, onClose, "#chat-q");

  function ask(text: string) {
    const t = text.trim();
    if (!t) return;
    const pendingId = ++nextId.current;
    setDraft("");
    setMessages((m) => [...m, { id: ++nextId.current, from: "me", text: t }, { id: pendingId, from: "bot", text: "", pending: true }]);
    // Ответ заменяет именно свой индикатор: вопросы можно задавать подряд, не дожидаясь ответа
    timers.current.push(
      window.setTimeout(() => {
        const r = mockReply(env, t);
        setMessages((m) => m.map((x) => (x.id === pendingId ? { id: pendingId, from: "bot", text: r.answer, basis: r.basis } : x)));
      }, 900),
    );
  }

  useEffect(() => {
    if (seed && !seeded.current) {
      seeded.current = true;
      ask(seed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(window.clearTimeout);
  }, []);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const suggestions = [
    ...env.card.open_questions,
    ...(env.card.role === "treasurer" ? [] : ["Как это выглядит для казначея?"]),
  ].slice(0, 3);

  return (
    <>
      <button type="button" className="panel-back" aria-label="Закрыть чат" onClick={onClose} />
      <aside ref={panel} className="panel !w-[480px]" role="dialog" aria-modal="true" aria-labelledby="ch-title">
        <div className="flex items-center justify-between gap-3 px-5 pt-5 pb-3">
          <h2 id="ch-title" className="m-0 text-[22px] leading-7 font-bold">
            Уточнить
          </h2>
          <button type="button" className="btn-icon" aria-label="Закрыть чат" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        <p className="muted m-0 mx-5 text-[14px] leading-5">
          Вопросы по событию «{env.card.headline}». Ответы учитывают профиль компании и вашу роль.
        </p>

        <div role="log" aria-live="polite" className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <p className="muted m-0 text-[14px]">Спросите про срок, другой разрез или влияние на конкретные платежи.</p>
          ) : null}
          {messages.map((m) =>
            m.from === "me" ? (
              <div key={m.id} className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-accent px-4 py-3 text-[15px] leading-[22px] text-white">
                {m.text}
              </div>
            ) : m.pending ? (
              <div key={m.id} className="claim claim--ai flex-row items-center gap-2.5 self-start !p-4">
                <span className="size-4 animate-spin rounded-full border-2 border-[#d2d3d9] border-t-[#1d5bbf]" aria-hidden="true" />
                <span className="muted text-[14px]">Сверяем с аналитикой банка…</span>
              </div>
            ) : (
              <div key={m.id} className="claim claim--ai max-w-[92%] self-start !p-4 text-[15px] leading-[22px]">
                <ClaimLabel type="ai" />
                <span>{m.text}</span>
                {m.basis ? (
                  <span className="flex flex-wrap items-center gap-1.5 text-[13px] text-ink-2">
                    Основание:
                    <span className="inline-flex h-[22px] items-center rounded-md border border-line bg-white px-2 text-[12px] font-semibold">
                      {CHAT_BASIS_LABEL[m.basis] ?? "Источник"}
                    </span>
                  </span>
                ) : null}
              </div>
            ),
          )}
          <div ref={end} />
        </div>

        <div className="flex flex-col gap-2.5 border-t border-line-2 px-5 pt-3 pb-4">
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                className="inline-flex min-h-[34px] items-center rounded-[17px] border border-line bg-white px-3 py-1.5 text-left text-[14px] leading-5 transition-colors hover:bg-field"
              >
                {s}
              </button>
            ))}
          </div>
          <form
            className="flex items-end gap-2 rounded-[14px] bg-field py-1.5 pr-1.5 pl-4 focus-within:bg-white focus-within:outline focus-within:outline-1 focus-within:outline-accent"
            onSubmit={(e) => {
              e.preventDefault();
              ask(draft);
            }}
          >
            <label htmlFor="chat-q" className="sr">
              Ваш вопрос
            </label>
            <textarea
              id="chat-q"
              rows={1}
              value={draft}
              placeholder="Задайте вопрос по событию"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(draft);
                }
              }}
              className="min-h-10 flex-1 resize-none border-0 bg-transparent py-2 text-[15px] leading-[22px] outline-none placeholder:text-muted"
            />
            <button
              type="submit"
              aria-label="Отправить"
              disabled={!draft.trim()}
              className="grid size-10 place-items-center rounded-[10px] bg-accent text-white disabled:cursor-not-allowed disabled:bg-[#d2d3d9]"
            >
              <Icon name="send" />
            </button>
          </form>
          <span className="muted text-[12px] leading-4">Аналитика не является инвестиционной рекомендацией</span>
        </div>
      </aside>
    </>
  );
}
