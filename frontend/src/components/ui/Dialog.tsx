"use client";

import { useRef } from "react";
import { useModal } from "@/lib/useModal";
import { Icon } from "./Icon";

/** Модальное окно: закрывается по Esc и клику на фон, фокус остаётся внутри и возвращается назад */
export function Dialog({
  title,
  onClose,
  children,
  labelId = "dlg-title",
  initialFocus = "textarea, input, button:not(.dlg-x)",
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  labelId?: string;
  /** Селектор элемента, на который встаёт фокус при открытии */
  initialFocus?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useModal(ref, onClose, initialFocus);

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
