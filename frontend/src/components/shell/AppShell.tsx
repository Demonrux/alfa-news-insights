"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/session";
import { AppHeader } from "./AppHeader";
import { SideNav } from "./SideNav";

/** Оболочка интернет-банка: шапка, меню, область страницы. Без входа отправляет на экран логина */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { ready, authed } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (ready && !authed) router.replace("/login");
  }, [ready, authed, router]);

  if (!ready || !authed) {
    return <div className="shell" aria-busy="true" />;
  }

  return (
    <div className="shell">
      <AppHeader />
      <div className="shell-body">
        <SideNav />
        <main className="shell-main">{children}</main>
      </div>
    </div>
  );
}
