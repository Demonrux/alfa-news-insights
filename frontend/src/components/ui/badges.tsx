import { Icon, type IconName } from "./Icon";
import {
  CLAIM_LABEL,
  MATERIALITY_LABEL,
  MATERIALITY_LEVEL,
  OVERALL_IMPACT_LABEL,
} from "@/lib/labels";
import type { Materiality, OverallImpact } from "@/lib/types";

const TYPE_CLASS: Record<OverallImpact, string> = {
  negative: "b-risk",
  positive: "b-opp",
  mixed: "b-mix",
  neutral: "b-neutral",
};

/** Тип события: подпись плюс маркер, у каждого типа своя форма (круг, половина, кольцо), а не только цвет */
export function TypeBadge({ type, large = false }: { type: OverallImpact; large?: boolean }) {
  return (
    <span className={`badge ${TYPE_CLASS[type]} ${large ? "badge--l" : ""}`}>
      <span className="badge-dot" aria-hidden="true" />
      {OVERALL_IMPACT_LABEL[type]}
    </span>
  );
}

/** Уровень влияния: три столбика и подпись */
export function ImpactLevel({
  level,
  short = false,
  strong = false,
}: {
  level: Materiality;
  short?: boolean;
  strong?: boolean;
}) {
  const n = MATERIALITY_LEVEL[level];
  return (
    <span className={`imp ${strong ? "imp--strong" : ""}`}>
      <span className={`bars l${n}`} aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {short ? MATERIALITY_LABEL[level] : `Влияние: ${MATERIALITY_LABEL[level].toLowerCase()}`}
    </span>
  );
}

export type ClaimType = "fact" | "bank" | "ai" | "hypothesis";

const CLAIM_ICON: Record<ClaimType, IconName> = {
  fact: "file",
  bank: "bank",
  ai: "sparkle",
  hypothesis: "help",
};
const CLAIM_CLS: Record<ClaimType, string> = {
  fact: "claim-label--fact",
  bank: "claim-label--bank",
  ai: "claim-label--ai",
  hypothesis: "claim-label--hyp",
};

/** Подпись типа утверждения: иконка и текст из disclaimers.yaml, у позиции банка можно добавить отчёт и дату */
export function ClaimLabel({
  type,
  title,
  sub,
}: {
  type: ClaimType;
  title?: string;
  sub?: string;
}) {
  return (
    <span className={`claim-label ${CLAIM_CLS[type]}`}>
      <Icon name={CLAIM_ICON[type]} size={16} />
      <span>
        <span className="t">{title ?? CLAIM_LABEL[type]}</span>
        {sub ? <span className="sub">{sub}</span> : null}
      </span>
    </span>
  );
}

/** Рамка блока утверждения: тип определяет вид рамки */export function ClaimBox({
  type,
  children,
  className = "",
}: {
  type: ClaimType;
  children: React.ReactNode;
  className?: string;
}) {
  const cls = { fact: "claim--fact", bank: "claim--bank", ai: "claim--ai", hypothesis: "claim--hyp" }[type];
  return <div className={`claim ${cls} ${className}`}>{children}</div>;
}
