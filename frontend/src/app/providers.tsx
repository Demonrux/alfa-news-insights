"use client";

import { ToastHost } from "@/components/ui/ToastHost";
import { SessionProvider } from "@/lib/session";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      {children}
      <ToastHost />
    </SessionProvider>
  );
}
