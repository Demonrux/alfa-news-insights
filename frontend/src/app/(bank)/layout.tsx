import { AppShell } from "@/components/shell/AppShell";

export default function BankLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
