"use client";

import { useState } from "react";
import { Button } from "@alfalab/core-components/button";
import { Dialog } from "@/components/ui/Dialog";
import { submitContact } from "@/lib/api";
import { CTA_LABEL, CTA_SUBMIT } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { ContactKind } from "@/lib/types";

/**
 * Обращение к менеджеру. Три варианта (связаться, оставить заявку, заказать звонок) отличаются только
 * заголовком и кнопкой: тип приходит в поле action.cta карточки. Для дайджеста события нет, поэтому
 * вместо события в сводке стоит период, а строка продукта скрыта.
 */
export function ContactDialog({
  kind,
  cardId,
  eventTitle,
  product,
  onClose,
}: {
  kind: ContactKind;
  cardId: string | null;
  eventTitle: string;
  product?: string | null;
  onClose: () => void;
}) {
  const { toast } = useSession();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    setBusy(true);
    await submitContact(cardId, kind, comment);
    toast("Заявка отправлена менеджеру", { label: "Отменить", run: () => toast("Заявка отозвана") });
    onClose();
  }

  return (
    <Dialog title={CTA_LABEL[kind]} onClose={onClose} labelId="contact-title">
      <dl className="summary m-0">
        <dt>{cardId ? "Событие" : "Период"}</dt>
        <dd>{eventTitle}</dd>
        {product ? (
          <>
            <dt>Продукт банка</dt>
            <dd>{product}</dd>
          </>
        ) : null}
      </dl>
      <label className="fld">
        <span className="font-semibold">Комментарий</span>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Что важно учесть менеджеру. Можно оставить пустым"
        />
      </label>
      <div className="dlg-actions">
        <Button view="primary" size={48} onClick={send} loading={busy}>
          {CTA_SUBMIT[kind]}
        </Button>
        <Button view="secondary" size={48} onClick={onClose}>
          Отмена
        </Button>
      </div>
    </Dialog>
  );
}
