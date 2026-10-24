"use client";

import { useState } from "react";
import { EventsWidget } from "@/components/home/EventsWidget";
import { Icon } from "@/components/ui/Icon";

const TABS = ["Сводка", "Счета на главной", "Мультибанк", "Металлы"];

/**
 * Главная интернет-банка. Наш модуль здесь один: виджет «События для вашего бизнеса» (точка входа).
 * Остальное повторяет настоящую главную Альфа-Бизнеса как заглушки с плейсхолдерами, чтобы виджет
 * выглядел частью банка. Суммы и названия не выдуманы: стоят значения в квадратных скобках.
 */
export default function HomePage() {
  const [tab, setTab] = useState(0);
  const [shown, setShown] = useState(true);

  return (
    <div className="flex flex-col gap-6 !pt-0">
      <h1 className="sr">Главная</h1>

      <div className="flex flex-wrap gap-2.5" role="group" aria-label="Быстрые действия">
        {["Скачать выписку", "Импорт платежей", "Создать платёж", "Ещё"].map((t, i) => (
          <button
            key={t}
            type="button"
            className={`inline-flex h-10 items-center gap-2.5 rounded-xl px-[18px] text-[15px] font-medium whitespace-nowrap hover:bg-[var(--c-bg-hover)] ${
              i === 3 ? "bg-[var(--c-bg-field-hover)] px-5" : "bg-surface"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <section
        className="grid gap-3 rounded-[28px] bg-[#121213] p-3 text-white [grid-template-columns:minmax(0,1.85fr)_minmax(0,1fr)_minmax(0,.9fr)] max-[1100px]:grid-cols-2 max-[760px]:grid-cols-1"
        aria-label="Остатки и дела"
      >
        <div className="flex min-w-0 flex-col rounded-[20px] bg-white/[.07] px-[22px] py-5">
          <span className="text-[34px] leading-[42px] font-bold">[Остаток] RUB</span>
          <span className="mt-2 flex items-center gap-1.5 text-[15px] text-white/60">
            <Icon name="chevronRight" size={16} />[Сумма] RUB с овердрафтом
          </span>
          <span className="mt-3 flex flex-wrap items-center gap-2.5 text-[15px]">
            [Сумма] CNY <span className="text-white/60">·</span> [Сумма] KZT
            <span className="counter !bg-white/15">+N</span>
          </span>
          <span className="min-h-7 flex-1" />
          <div className="flex flex-wrap gap-4 border-t border-white/10 pt-4">
            <span className="flex flex-1 basis-44 items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-white/10">
                <Icon name="accounts" />
              </span>
              <span>
                <span className="block text-[15px]">Счета</span>
                <span className="text-[13px] text-white/60">[N] в рублях, [N] в валюте</span>
              </span>
            </span>
            <span className="flex flex-1 basis-44 items-center gap-3 text-[15px]">
              <span className="grid size-10 place-items-center rounded-xl bg-white/10">
                <Icon name="plus" />
              </span>
              Заказать бизнес-карту
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1 rounded-[20px] bg-white/[.07] px-[22px] py-5">
          <h2 className="m-0 mb-2.5 text-[16px] leading-[22px] font-bold">Дела в работе</h2>
          {[
            ["Подписать и отправить", true],
            ["В работе у банка", true],
            ["Отклонённые", true],
            ["Черновики", false],
            ["Оплатить", false],
            ["Принять предложение", false],
          ].map(([t, alert]) => (
            <span key={t as string} className="flex min-h-[35px] items-center justify-between gap-3 text-[15px]">
              {t}
              <span className={`counter ${alert ? "" : "!bg-white/15 !text-white/85"}`}>N</span>
            </span>
          ))}
        </div>
        <div className="flex flex-col gap-2 rounded-[20px] bg-gradient-to-br from-[#2b2b2f] via-[#1a1a1c] to-[#3a1512] px-[22px] py-5 max-[1100px]:hidden">
          <span className="text-[16px] leading-[22px] font-bold">[Промо-предложение банка]</span>
          <span className="text-[14px] leading-5 text-white/60">[Короткое описание]</span>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-7">
        <div role="tablist" aria-label="Разделы главной" className="flex min-w-0 flex-1 gap-7 overflow-x-auto">
          {TABS.map((t, i) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === i}
              onClick={() => setTab(i)}
              className={`text-[22px] leading-7 font-bold whitespace-nowrap max-[760px]:text-[18px] ${
                tab === i ? "text-ink" : "text-[#6e6e76] hover:text-ink-2"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="inline-flex gap-0.5 rounded-xl bg-[var(--c-bg-field-hover)] p-0.5" role="group" aria-label="Показ сумм">
          <button
            type="button"
            aria-pressed={shown}
            aria-label="Показывать суммы"
            onClick={() => setShown(true)}
            className={`grid size-9 place-items-center rounded-[10px] ${shown ? "bg-white shadow-sm" : "text-muted"}`}
          >
            <Icon name="eye" />
          </button>
          <button
            type="button"
            aria-pressed={!shown}
            aria-label="Скрыть суммы"
            onClick={() => setShown(false)}
            className={`grid size-9 place-items-center rounded-[10px] ${!shown ? "bg-white shadow-sm" : "text-muted"}`}
          >
            <Icon name="eyeOff" />
          </button>
        </div>
        <button type="button" className="iconbtn" aria-label="Настроить главную">
          <Icon name="gear" />
        </button>
      </div>

      {tab === 0 ? (
        <div className="grid grid-cols-3 items-start gap-4 max-[1100px]:grid-cols-2 max-[760px]:grid-cols-1">
          <EventsWidget />
          <section className="flex min-w-0 flex-col gap-3.5 rounded-[20px] bg-surface p-[22px]">
            <span className="flex items-center gap-2 text-[16px] leading-[22px] font-bold">
              Активные заявки <span className="chip !px-1.5 !py-0.5 text-[12px] font-bold">N</span>
            </span>
            {["Лизинг", "Факторинг"].map((t, i) => (
              <div key={t} className="flex flex-col gap-1 border-t border-line-2 pt-3 text-[14px]">
                <span className="font-semibold">{t}</span>
                <span className="flex items-center justify-between gap-2">
                  [Сумма] ₽
                  <span className="rounded-md bg-field px-1.5 py-0.5 text-[11px] font-bold tracking-wide uppercase text-ink-2">
                    {i === 0 ? "На подпись" : "В работе"}
                  </span>
                </span>
                <span className="muted text-[12px]">[дд.мм.гггг]</span>
              </div>
            ))}
          </section>
          <section className="flex min-w-0 flex-col gap-3.5 rounded-[20px] bg-surface p-[22px]">
            <span className="text-[16px] leading-[22px] font-bold">Индикатор риска</span>
            <div
              className="mx-auto mt-1 h-[90px] w-[180px] rounded-t-[180px] border-[12px] border-b-0 border-[var(--c-bg-field)]"
              aria-hidden="true"
            />
            <span className="-mt-2 text-center text-[16px] font-bold">[Уровень риска]</span>
            <span className="muted text-center text-[13px]">[Пояснение к индикатору]</span>
          </section>
          <section className="flex min-w-0 flex-col gap-3.5 rounded-[20px] bg-surface p-[22px]">
            <span className="text-[16px] leading-[22px] font-bold">Конвертация</span>
            <table className="w-full border-collapse text-[14px]">
              <thead>
                <tr className="muted text-[13px]">
                  <th className="pb-2 text-left font-medium">Валюта</th>
                  <th className="pb-2 text-right font-medium">Продать</th>
                  <th className="pb-2 text-right font-medium">Купить</th>
                </tr>
              </thead>
              <tbody>
                {["CNY/RUB", "EUR/RUB", "USD/RUB"].map((p) => (
                  <tr key={p} className="border-t border-line-2">
                    <td className="py-2">{p}</td>
                    <td className="py-2 text-right">[курс]</td>
                    <td className="py-2 text-right">[курс]</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      ) : (
        <section className="rounded-[20px] bg-surface p-[22px]">
          <span className="text-[16px] font-bold">{TABS[tab]}</span>
          <p className="muted m-0 mt-1 text-[14px]">Раздел банка, в макете не детализирован</p>
        </section>
      )}
    </div>
  );
}
