"use client";

import { useState } from "react";
import Link from "next/link";
import { RoleDialog } from "@/components/dialogs/RoleDialog";
import { ErrorState } from "@/components/states/StateBlock";
import { ImpactLevel, TypeBadge } from "@/components/ui/badges";
import { FACTOR_LABEL, roleName } from "@/lib/labels";
import { formatRelative } from "@/lib/format";
import { useFeed } from "@/lib/hooks";
import { useSession } from "@/lib/session";

/** Заметная точка входа в сервис на главной: три главных события для компании и роли */
export function EventsWidget() {
  const { company, role, hidden } = useSession();
  const { state, loading, reload } = useFeed();
  const [roleOpen, setRoleOpen] = useState(false);

  const items = state.status === "ready" ? state.data.filter((i) => !hidden[i.id]).slice(0, 3) : [];

  return (
    <section className="card card--wide col-span-2 flex flex-col gap-5 rounded-[20px] bg-surface p-[22px]" aria-labelledby="w-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="w-title" className="m-0 flex flex-wrap items-center gap-2.5 text-[18px] leading-6 font-bold">
            События для вашего бизнеса
            <span className="badge-new">Новое</span>
          </h2>
          <p className="muted m-0 text-[14px] leading-5">
            Три главных события для {company?.name}. Выводы для роли «{roleName(role)}».{" "}
            <button type="button" className="lnk !p-0 !text-[14px]" onClick={() => setRoleOpen(true)} aria-haspopup="dialog">
              Сменить
            </button>
          </p>
        </div>
        <Link href="/analytics" className="btn btn-primary">
          Все события
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2.5" aria-hidden="true">
          <div className="skeleton h-16" />
          <div className="skeleton h-16" />
          <div className="skeleton h-16" />
        </div>
      ) : state.status === "error" ? (
        <ErrorState error={state.error} onRetry={reload} />
      ) : items.length === 0 ? (
        <p className="muted m-0 text-[15px]">Пока нет событий для {company?.name}. Покажем их, когда найдём важное.</p>
      ) : (
        <div className="flex flex-col">
          {items.map((e) => (
            <Link
              key={e.id}
              href={`/analytics/${e.id}`}
              className="group grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 border-t border-line-2 py-3.5 first:border-t-0"
            >
              <span className="flex flex-wrap items-center gap-2.5">
                <TypeBadge type={e.overallImpact} />
                <span className="muted text-[13px]">
                  {FACTOR_LABEL[e.factor]}, {formatRelative(e.createdAt).toLowerCase()}
                </span>
              </span>
              <span className="row-span-2 self-center">
                <ImpactLevel level={e.materiality} short />
              </span>
              <span className="text-[16px] leading-[22px] font-bold group-hover:underline">{e.headline}</span>
            </Link>
          ))}
        </div>
      )}
      {roleOpen ? <RoleDialog onClose={() => setRoleOpen(false)} /> : null}
    </section>
  );
}
