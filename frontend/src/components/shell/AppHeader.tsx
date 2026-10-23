"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { Select } from "@/components/ui/Select";
import { UI_ROLES, roleName, uiRole } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { CompanySwitcher } from "./CompanySwitcher";

const ROLE_OPTIONS = UI_ROLES.map((r) => ({ value: r.code, label: r.name }));

export function AppHeader() {
  const { me, role, selectRole, signOut, toast } = useSession();
  const router = useRouter();

  return (
    <header className="top">
      <Link href="/" className="brand" aria-label="Альфа-Бизнес, на главную">
        <span className="logo" role="img" aria-label="Логотип, заглушка" />
        <span className="brand-name">Альфа-Бизнес</span>
      </Link>

      <div className="flex-1" />

      <Select
        className="dd--role"
        label="Ваша роль в компании"
        prefix="Роль"
        align="end"
        value={uiRole(role)}
        options={ROLE_OPTIONS}
        onChange={(next) => {
          selectRole(next);
          toast(`Выводы показаны для роли «${roleName(next)}»`);
        }}
      />

      <button type="button" className="iconbtn" aria-label="Сообщения">
        <Icon name="mail" />
      </button>
      <button type="button" className="iconbtn" aria-label="Уведомления, есть новые">
        <Icon name="bell" />
        <span className="dot" />
      </button>

      <CompanySwitcher />

      <button type="button" className="user-pill" aria-label="Профиль пользователя">
        <span className="ava" aria-hidden="true">
          {me?.person.initials ?? "И"}
        </span>
        <span className="nm">{me?.person.fullName ?? "Пользователь"}</span>
      </button>
      <span className="vsep" aria-hidden="true" />
      <button
        type="button"
        className="iconbtn"
        aria-label="Выйти"
        onClick={() => {
          signOut();
          router.replace("/login");
        }}
      >
        <Icon name="logout" />
      </button>
    </header>
  );
}
