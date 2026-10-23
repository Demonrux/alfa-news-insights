import type { CardEnvelope, SourceInfo } from "@/lib/types";

/** Все ссылки на источники в карточке: новости, внешние публикации и тезисы банка. Признаки и контрагентов пропускаем */
function refsOf(env: CardEnvelope): string[] {
  const c = env.card;
  const all = [
    ...c.what_happened.flatMap((w) => w.source_ids),
    ...c.bank_view.map((b) => b.thesis_id),
    ...c.ai_conclusions.flatMap((x) => x.based_on),
    ...c.hypotheses.flatMap((x) => x.based_on),
    ...c.risks.flatMap((x) => x.based_on),
    ...c.opportunities.flatMap((x) => x.based_on),
    ...(c.impact.estimate?.based_on ?? []),
  ];
  return [...new Set(all)].filter((id) => !id.startsWith("feature:") && !id.startsWith("cp:"));
}

/** Источники, которые удалось превратить в названия. Остальные коды пользователю не показываем */
export function collectSources(env: CardEnvelope): SourceInfo[] {
  return refsOf(env)
    .map((id) => env.sources[id])
    .filter((s): s is SourceInfo => !!s);
}

/** Источники конкретного списка кодов (например, у блока «Что произошло») */
export function sourcesFor(env: CardEnvelope, ids: string[]): SourceInfo[] {
  return [...new Set(ids)].map((id) => env.sources[id]).filter((s): s is SourceInfo => !!s);
}
