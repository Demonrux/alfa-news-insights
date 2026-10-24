"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  value: T;
  options: readonly SelectOption<T>[];
  onChange: (value: T) => void;
  /** Что выбираем: читает скринридер, подписывает список */
  label: string;
  /** Видимая приставка перед значением, например «Роль» */
  prefix?: string;
  /** ghost: без рамки, для шапки. pill: таблетка для фильтров */
  variant?: "ghost" | "pill";
  /** С какого края триггера открывается список */
  align?: "start" | "end";
  className?: string;
}

const TYPEAHEAD_RESET_MS = 600;

/**
 * Выпадающий список вместо системного select: единый вид, анимация и управление с клавиатуры.
 * Паттерн ARIA «select-only combobox»: фокус остаётся на кнопке, активный пункт указан в aria-activedescendant.
 */
export function Select<T extends string>({
  value,
  options,
  onChange,
  label,
  prefix,
  variant = "ghost",
  align = "start",
  className = "",
}: Props<T>) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const typed = useRef({ text: "", timer: 0 });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const selected = options[selectedIndex];
  const optionId = (i: number) => `${id}-opt-${i}`;

  function show() {
    setActive(selectedIndex);
    setOpen(true);
  }

  function choose(i: number) {
    setOpen(false);
    if (options[i].value !== value) onChange(options[i].value);
  }

  // Закрываем по клику снаружи
  useEffect(() => {
    if (!open) return;
    const close = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  // На узких экранах список не должен выходить за край окна: сдвигаем его после первого замера
  useLayoutEffect(() => {
    const pop = list.current;
    if (!open || !pop) return;
    const { left, right } = pop.getBoundingClientRect();
    const edge = 16;
    const dx = right > window.innerWidth - edge ? window.innerWidth - edge - right : Math.max(0, edge - left);
    // translate не конфликтует с transform из анимации появления
    pop.style.translate = dx ? `${dx}px 0` : "";
  }, [open]);

  // Активный пункт всегда в зоне видимости
  useEffect(() => {
    if (open) list.current?.children[active]?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  useEffect(() => () => window.clearTimeout(typed.current.timer), []);

  function onKeyDown(e: React.KeyboardEvent<HTMLButtonElement>) {
    const last = options.length - 1;
    switch (e.key) {
      case "ArrowDown":
      case "ArrowUp": {
        e.preventDefault();
        if (!open) return show();
        const step = e.key === "ArrowDown" ? 1 : -1;
        setActive((a) => Math.min(last, Math.max(0, a + step)));
        return;
      }
      case "Home":
      case "End":
        if (!open) return;
        e.preventDefault();
        setActive(e.key === "Home" ? 0 : last);
        return;
      case "Enter":
      case " ":
        e.preventDefault();
        return open ? choose(active) : show();
      case "Escape":
        if (open) {
          e.preventDefault();
          setOpen(false);
        }
        return;
      case "Tab":
        setOpen(false);
        return;
    }
    // Быстрый переход по первым буквам
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const t = typed.current;
      window.clearTimeout(t.timer);
      t.text += e.key.toLowerCase();
      t.timer = window.setTimeout(() => (t.text = ""), TYPEAHEAD_RESET_MS);
      const from = open ? active : selectedIndex;
      // Повтор одной буквы листает по кругу от следующего пункта, разные буквы уточняют текущий
      const repeated = [...t.text].every((ch) => ch === t.text[0]);
      const prefix = repeated ? t.text[0] : t.text;
      const skip = repeated ? 1 : 0;
      const order = Array.from({ length: options.length }, (_, k) => (from + skip + k) % options.length);
      const hit = order.find((i) => options[i].label.toLowerCase().startsWith(prefix));
      if (hit !== undefined) {
        if (!open) setOpen(true);
        setActive(hit);
      }
    }
  }

  return (
    <div ref={root} className={`dd dd--${variant} dd--${align} ${className}`}>
      <button
        type="button"
        role="combobox"
        className="dd-btn"
        aria-label={`${prefix ?? label}: ${selected.label}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-activedescendant={open ? optionId(active) : undefined}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKeyDown}
      >
        {prefix ? <span className="dd-pre">{prefix}</span> : null}
        <span className="dd-val">{selected.label}</span>
        <Icon name="chevronDown" size={18} className="dd-chev" />
      </button>

      {open ? (
        <ul ref={list} id={`${id}-list`} role="listbox" aria-label={label} className="dd-pop">
          {options.map((o, i) => (
            <li
              key={o.value}
              id={optionId(i)}
              role="option"
              aria-selected={o.value === value}
              data-active={i === active}
              className="dd-opt"
              // mousedown не должен уводить фокус с кнопки
              onMouseDown={(e) => e.preventDefault()}
              onMouseMove={() => i !== active && setActive(i)}
              onClick={() => choose(i)}
            >
              {o.label}
              {o.value === value ? <Icon name="check" size={18} /> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
