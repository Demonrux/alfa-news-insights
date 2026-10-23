"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { roleName } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { defaultRole } from "@/lib/api";

/** Поиск в списке появляется от этого числа компаний */
const SEARCH_FROM = 8;

/** Единственное место смены компании: последняя выбранная запоминается и открывается при входе */
export function CompanySwitcher() {
  const { me, company, selectCompany, switcherRequest } = useSession();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const lastReq = useRef(switcherRequest);

  // «Выбрать другую компанию» из состояния «Нет доступа» открывает этот список
  useEffect(() => {
    if (switcherRequest !== lastReq.current) {
      lastReq.current = switcherRequest;
      setOpen(true);
    }
  }, [switcherRequest]);

  useEffect(() => {
    if (open) pop.current?.querySelector<HTMLElement>('[aria-current="true"], .cs-it')?.focus();
  }, [open]);

  const companies = useMemo(() => me?.companies ?? [], [me]);
  const q = query.trim().toLowerCase();
  const groups = useMemo(() => {
    const names = [...new Set(companies.map((c) => c.group))];
    return names
      .map((g) => ({
        name: g,
        items: companies.filter(
          (c) => c.group === g && (!q || `${c.name} ${c.activity} ${c.label}`.toLowerCase().includes(q)),
        ),
      }))
      .filter((g) => g.items.length);
  }, [companies, q]);

  if (!company || !me) return null;
  const single = companies.length === 1;

  const head = (
    <>
      <span className="co-logo" aria-hidden="true">
        {company.short}
      </span>
      <span className="flex flex-col" title={company.activity}>
        <span className="text-[14px] leading-[18px] font-bold">{company.name}</span>
        <span className="muted text-[12px] leading-4">{me.person.fullName}</span>
      </span>
    </>
  );

  if (single) return <div className="csw"><div className="cosw cosw--static">{head}</div></div>;

  const close = () => {
    setOpen(false);
    setQuery("");
    trigger.current?.focus();
  };

  return (
    <div
      className="csw"
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          close();
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="cosw"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`Сменить компанию. Сейчас: ${company.name}, ${company.activity.toLowerCase()}`}
        onClick={() => setOpen((v) => !v)}
      >
        {head}
        <Icon name="chevronDown" size={16} className="chev" />
      </button>

      {open ? (
        <>
          <button type="button" className="cs-back" aria-label="Закрыть выбор компании" onClick={close} />
          <div ref={pop} className="cs-pop" role="dialog" aria-label="Выбор компании">
            {companies.length >= SEARCH_FROM ? (
              <label className="cs-search">
                <Icon name="search" size={16} />
                <span className="sr">Поиск компании</span>
                <input
                  type="search"
                  placeholder="Название или вид деятельности"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
            ) : null}
            <div className="cs-list">
              {groups.map((g) => (
                <div key={g.name} className="contents">
                  <div className="cs-gh">{g.name}</div>
                  {g.items.map((c) => {
                    const on = c.id === company.id;
                    const meta = `${c.label.split(" · ")[0]} · ${roleName(defaultRoleFor(c.id))}`;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        className="cs-it"
                        aria-current={on}
                        aria-label={`${c.name}, ${meta}${c.newEvents ? `, новых событий: ${c.newEvents}` : ""}${on ? ", выбрана" : ""}`}
                        onClick={() => {
                          selectCompany(c.id);
                          close();
                        }}
                      >
                        <span className="co-logo" aria-hidden="true">
                          {c.short}
                        </span>
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <span className="text-[15px] font-bold">{c.name}</span>
                          <span className="cs-meta">{meta}</span>
                        </span>
                        <span className="cs-check">{on ? <Icon name="check" /> : null}</span>
                        <span className="cs-count">
                          {c.newEvents > 0 ? <span className="counter">{c.newEvents}</span> : null}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))}
              {groups.length === 0 ? (
                <p className="cs-meta m-0 px-3 py-4">Ничего не нашли. Попробуйте другой вид деятельности.</p>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function defaultRoleFor(id: string) {
  return defaultRole(id);
}
