"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useSession } from "@/lib/session";

interface Item {
  label: string;
  /** Полное название для скринридера и подсказки, если в меню оно сокращено */
  fullLabel?: string;
  icon: IconName;
  href?: string;
  lead?: boolean;
  muted?: boolean;
  isNew?: boolean;
  counter?: boolean;
  sepBefore?: boolean;
  spacerBefore?: boolean;
}

/** Меню настоящего Альфа-Бизнеса. Работает только наш пункт, остальные заглушки банка */
const ITEMS: Item[] = [
  { label: "Все сервисы", icon: "grid", lead: true },
  { label: "Заявки", icon: "doc", isNew: true, sepBefore: true },
  { label: "Аналитика", fullLabel: "Аналитика для бизнеса", icon: "bell", href: "/analytics", isNew: true, counter: true },
  { label: "Новый платёж", icon: "plus" },
  { label: "Лента операций", icon: "list" },
  { label: "Платежи в работе", icon: "clockCircle" },
  { label: "Импорт реестров", icon: "download" },
  { label: "Выписка", icon: "file" },
  { label: "Счета", icon: "accounts" },
  { label: "Контрагенты", icon: "people" },
  { label: "Справки", icon: "doc" },
  { label: "Счета на оплату", icon: "receipt" },
  { label: "Карты", icon: "card" },
  { label: "Госзакупки", icon: "gov", sepBefore: true },
  { label: "Настроить меню", icon: "gear", muted: true, spacerBefore: true },
];

export function SideNav() {
  const path = usePathname();
  const { company } = useSession();
  const events = company?.newEvents ?? 0;

  return (
    <nav className="side" aria-label="Разделы банка">
      {ITEMS.map((it) => {
        const current = it.href ? path.startsWith(it.href) : false;
        const cls = `nav ${it.lead ? "nav--lead" : ""} ${it.muted ? "nav--muted" : ""}`;
        const inner = (
          <>
            <Icon name={it.icon} />
            <span className="lbl truncate">{it.label}</span>
            {it.isNew || (it.counter && events > 0) ? (
              <span className="nav-end">
                {it.counter && events > 0 ? (
                  <>
                    <span className="counter" aria-hidden="true">
                      {events}
                    </span>
                    <span className="sr">, новых событий: {events}</span>
                  </>
                ) : null}
                {it.isNew ? <span className="badge-new">Новое</span> : null}
              </span>
            ) : null}
          </>
        );
        return (
          <div key={it.label} className="contents">
            {it.sepBefore ? <span className="nav-sep" aria-hidden="true" /> : null}
            {it.spacerBefore ? <span className="side-spacer" aria-hidden="true" /> : null}
            {it.href ? (
              <Link
                href={it.href}
                className={cls}
                title={it.fullLabel}
                aria-label={it.fullLabel ? `${it.fullLabel}${events > 0 && it.counter ? `, новых событий: ${events}` : ""}` : undefined}
                aria-current={current ? "page" : undefined}
              >
                {inner}
              </Link>
            ) : (
              <a href="#" className={cls} onClick={(e) => e.preventDefault()}>
                {inner}
              </a>
            )}
          </div>
        );
      })}
    </nav>
  );
}
