"use client";

import { useEffect, useRef } from "react";
import { Icon } from "./Icon";

/** Модальное окно: закрывается по Esc и клику на фон, фокус уходит внутрь и возвращается назад */
export function Dialog({
  title,
  onClose,
  children,
  labelId = "dlg-title",
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  labelId?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>("textarea, input, button:not(.dlg-x)");
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [onClose]);

  return (
    <div className="dlg-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className="dlg" role="dialog" aria-modal="true" aria-labelledby={labelId}>
        <div className="dlg-h">
          <h2 id={labelId}>{title}</h2>
          <button type="button" className="dlg-x" aria-label="Закрыть" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
