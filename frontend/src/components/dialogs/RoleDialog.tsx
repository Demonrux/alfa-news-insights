"use client";

import { useState } from "react";
import { Button } from "@alfalab/core-components/button";
import { Dialog } from "@/components/ui/Dialog";
import { UI_ROLES, roleName, uiRole } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { RoleCode } from "@/lib/types";

/** Смена роли по кнопке «Сменить» в виджете. Роль хранится для пары «человек + компания» */
export function RoleDialog({ onClose }: { onClose: () => void }) {
  const { company, role, selectRole, toast } = useSession();
  const [picked, setPicked] = useState<RoleCode>(uiRole(role));

  return (
    <Dialog title={`Ваша роль в ${company?.name ?? "компании"}`} onClose={onClose} labelId="role-title">
      <p className="muted m-0 text-[14px] leading-5">
        Запомним для этой компании. От роли зависят выводы в карточках. На доступ к банку она не влияет.
      </p>
      <div role="radiogroup" aria-label="Роль" className="flex flex-col gap-2">
        {UI_ROLES.map((r) => (
          <label key={r.code} className={`role-opt ${picked === r.code ? "on" : ""}`}>
            <input type="radio" name="role" checked={picked === r.code} onChange={() => setPicked(r.code)} />
            <span className="cs-radio" aria-hidden="true" />
            <span className="flex flex-col gap-0.5">
              <span className="text-[15px] font-semibold">{r.name}</span>
              <span className="cs-meta">{r.focus}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="dlg-actions">
        <Button
          view="primary"
          size={48}
          onClick={() => {
            selectRole(picked);
            toast(`Выводы показаны для роли «${roleName(picked)}»`);
            onClose();
          }}
        >
          Сохранить
        </Button>
        <Button view="secondary" size={48} onClick={onClose}>
          Отмена
        </Button>
      </div>
    </Dialog>
  );
}
