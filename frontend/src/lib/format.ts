const DAY = 24 * 60 * 60 * 1000;

/** «Сегодня, 10:40», «Вчера», «3 дня назад», «11 сентября» */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((start(now) - start(d)) / DAY);
  const time = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  if (diff <= 0) return `Сегодня, ${time}`;
  if (diff === 1) return "Вчера";
  if (diff < 7) return `${diff} ${plural(diff, ["день", "дня", "дней"])} назад`;
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function plural(n: number, forms: [string, string, string]): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return forms[0];
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return forms[1];
  return forms[2];
}

/** Позиция банка могла устареть: старше порога в днях (порог зададим вместе с командой) */
export function isStale(reportDate: string, now: Date = new Date(), thresholdDays = 60): boolean {
  return (now.getTime() - new Date(reportDate).getTime()) / DAY > thresholdDays;
}
