"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@alfalab/core-components/button";
import { Input } from "@alfalab/core-components/input";
import { PasswordInput } from "@alfalab/core-components/password-input";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useSession } from "@/lib/session";

const OTHER_WAYS: { label: string; icon: IconName }[] = [
  { label: "Быстрый вход", icon: "grid" },
  { label: "Логин", icon: "lock" },
  { label: "QR-код", icon: "search" },
  { label: "Токен", icon: "link" },
];

/** Вход как в Альфа-Бизнесе: по человеку, а не по компании. В демо подойдут любые данные */
export default function LoginPage() {
  const { ready, authed, signIn } = useSession();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && authed) router.replace("/");
  }, [ready, authed, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    await signIn(phone, password);
    router.replace("/");
  }

  return (
    <div className="flex min-h-screen flex-col bg-white px-4 pt-4 pb-8">
      <header className="flex items-center justify-between">
        <span className="logo" role="img" aria-label="Логотип, заглушка" />
        <a href="#" className="px-3 py-2 text-[18px] font-medium" onClick={(e) => e.preventDefault()}>
          Помощь
        </a>
      </header>

      <main className="flex flex-1 items-center justify-center py-12">
        <form onSubmit={submit} className="flex w-full max-w-[400px] flex-col gap-4">
          <div className="mb-4 text-center">
            <h1 className="m-0 mb-3 text-[40px] leading-[48px] font-bold tracking-[-0.5px]">Альфа-Бизнес</h1>
            <p className="m-0 text-[16px] leading-6">Вход по Alfa ID</p>
          </div>
          <Input
            label="Телефон"
            type="tel"
            block
            size={56}
            value={phone}
            onChange={(_, { value }) => setPhone(value)}
            autoComplete="tel"
          />
          <PasswordInput
            label="Пароль"
            block
            size={56}
            value={password}
            onChange={(_, { value }) => setPassword(value)}
            autoComplete="current-password"
          />
          <p className="muted m-0 -mt-1 text-center text-[13px] leading-[18px]">
            Демо-режим: подойдут любые данные. Компанию можно сменить в шапке после входа.
          </p>
          <Button type="submit" view="primary" size={56} block loading={busy} className="mt-4">
            Войти
          </Button>
          <div className="mt-2 text-center">
            <a href="#" className="text-[16px] font-semibold hover:underline" onClick={(e) => e.preventDefault()}>
              Забыли пароль?
            </a>
          </div>
        </form>
      </main>

      <nav aria-label="Другие способы входа" className="flex flex-wrap justify-center gap-3">
        {OTHER_WAYS.map((w) => (
          <a
            key={w.label}
            href="#"
            onClick={(e) => e.preventDefault()}
            className="flex w-24 flex-col items-center gap-2.5 text-[14px] font-semibold"
          >
            <span className="grid size-12 place-items-center rounded-full bg-field">
              <Icon name={w.icon} size={22} />
            </span>
            {w.label}
          </a>
        ))}
      </nav>
    </div>
  );
}
