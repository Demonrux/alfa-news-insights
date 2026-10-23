"use client";

import { useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { ImpactLevel, TypeBadge } from "@/components/ui/badges";
import { BADGE_EXTERNAL, FACTOR_LABEL } from "@/lib/labels";
import { formatRelative } from "@/lib/format";
import type { FeedItem } from "@/lib/types";

/** Карточка в ленте: заголовок-вывод, «почему вы видите», источники и меню «скрыть / не релевантно» */
export function FeedCard({
  item,
  onHide,
  onIrrelevant,
}: {
  item: FeedItem;
  onHide: () => void;
  onIrrelevant: () => void;
}) {
  const [menu, setMenu] = useState(false);

  return (
    <article className="feed-card">
      <div className="flex flex-wrap items-center gap-3">
        <TypeBadge type={item.overallImpact} />
        <ImpactLevel level={item.materiality} />
        <span className="muted text-[13px]">{FACTOR_LABEL[item.factor]}</span>
        {item.external ? <span className="tag-ext">{BADGE_EXTERNAL}</span> : null}
        <span className="flex-1" />
        {item.isNew ? <span className="newmark">Новое</span> : null}
        <span className="muted text-[13px]">{formatRelative(item.createdAt)}</span>
      </div>

      <Link href={`/analytics/${item.id}`} className="hl">
        {item.headline}
      </Link>

      <p className="why">
        <Icon name="info" size={16} className="mt-[3px]" />
        <span>Вы видите это, потому что {lowerFirst(item.whyLine)}</span>
      </p>

      <div className="flex items-center gap-2 border-t border-[var(--c-bg-field)] pt-2.5">
        <span className="muted flex-1 text-[13px]">{item.sourceLine}</span>
        <button
          type="button"
          className="more"
          aria-label="Действия с событием"
          aria-expanded={menu}
          onClick={() => setMenu((v) => !v)}
        >
          <Icon name="dots" />
        </button>
      </div>

      {menu ? (
        <div className="menu" role="menu">
          <button
            type="button"
            className="mi"
            role="menuitem"
            onClick={() => {
              setMenu(false);
              onHide();
            }}
          >
            <Icon name="eyeOff" size={16} />
            Скрыть
          </button>
          <button
            type="button"
            className="mi"
            role="menuitem"
            onClick={() => {
              setMenu(false);
              onIrrelevant();
            }}
          >
            <Icon name="ban" size={16} />
            Не релевантно
          </button>
        </div>
      ) : null}
    </article>
  );
}

function lowerFirst(s: string): string {
  return s ? s.charAt(0).toLowerCase() + s.slice(1) : s;
}
