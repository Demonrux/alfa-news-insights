import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@alfalab/core-components/vars/bundle/corp.css";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  variable: "--font-sans-app",
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: "Альфа-Бизнес: аналитика для бизнеса",
  description: "Персональные инсайты для руководителей крупного бизнеса",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
