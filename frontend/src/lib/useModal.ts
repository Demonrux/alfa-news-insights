"use client";

import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Поведение модального слоя: фокус уходит внутрь и не выходит по Tab, Esc закрывает,
 * страница под слоем не прокручивается, после закрытия фокус возвращается на то, что было в нём раньше.
 * initialFocus: селектор элемента, на который встаёт фокус при открытии (по умолчанию первый доступный).
 */
export function useModal(ref: RefObject<HTMLElement | null>, onClose: () => void, initialFocus?: string) {
  // onClose в ref: родитель может передавать новую функцию на каждый рендер, а слой не должен из-за этого терять фокус
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  });

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const opener = document.activeElement as HTMLElement | null;
    const items = () => [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);

    (root.querySelector<HTMLElement>(initialFocus ?? FOCUSABLE) ?? root).focus();

    const scroll = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close.current();
        return;
      }
      if (e.key !== "Tab") return;
      const list = items();
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !root.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !root.contains(active))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = scroll;
      opener?.focus();
    };
  }, [ref, initialFocus]);
}
