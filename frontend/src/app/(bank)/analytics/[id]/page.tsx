"use client";

import { useParams } from "next/navigation";
import { InsightView } from "@/components/insight/InsightView";
import { ErrorState, LoadingSteps } from "@/components/states/StateBlock";
import { useCard } from "@/lib/hooks";

/** Страница карточки. Пока агент готовит ответ, показываем шаги, а не пустой экран */
export default function InsightPage() {
  const { id } = useParams<{ id: string }>();
  const { state, reload } = useCard(id);

  if (state.status === "loading") return <LoadingSteps />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;
  return <InsightView env={state.data} />;
}
