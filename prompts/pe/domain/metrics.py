from __future__ import annotations

import math
from collections import defaultdict

JUDGE_KEYS = ("q1_what_happened", "q2_why_relevant", "q3_consequences", "q4_actions", "q5_bank_view", "q6_grounding")


def p1_metrics(rows: list[dict], expect: dict[str, dict]) -> dict:
    """Считает точность классификации P1"""
    n = hit = tp = fp = fn = rel_ok = rel_n = 0
    for row in rows:
        e = expect.get(row["case"], {})
        if row.get("primary") is None and "factors" not in row:
            continue
        if "is_business_relevant" in e:
            rel_n += 1
            rel_ok += bool(row.get("factors")) == e["is_business_relevant"]
        if e.get("primary_factor"):
            n += 1
            hit += row.get("primary") in [e["primary_factor"], *e.get("primary_alternatives", [])]
        gold = set(e.get("factors_include", [])) | ({e["primary_factor"]} if e.get("primary_factor") else set())
        pred = set(row.get("factors") or [])
        tp += len(pred & gold)
        fp += len(pred - gold - set(e.get("factors_optional", [])))
        fn += len(gold - pred)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"primary_acc": round(hit / n, 3) if n else None, "factor_P": round(prec, 3), "factor_R": round(rec, 3),
            "factor_F1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
            "relevance_acc": round(rel_ok / rel_n, 3) if rel_n else None}


def judge_summary(outputs: list[dict]) -> dict:
    """Считает средние оценки судьи"""
    vals, errors, retell = defaultdict(list), 0, 0
    for o in filter(None, outputs):
        for k in JUDGE_KEYS:
            if isinstance(o.get(k), int):
                vals[k].append(o[k])
        errors += len(o.get("factual_errors") or [])
        retell += bool(o.get("is_retelling"))
    n = max(len(vals[JUDGE_KEYS[0]]), 1)
    res = {k: round(sum(v) / len(v), 2) for k, v in vals.items() if v}
    present = [res[k] for k in JUDGE_KEYS if k in res]
    res.update(mean_all=round(sum(present) / max(len(present), 1), 2), factual_errors_per_card=round(errors / n, 2),
               retelling_share=round(retell / n, 3), cards=n)
    return res


def judge_agreement(judge: dict[str, dict], human: dict[str, dict]) -> dict:
    """Сравнивает оценки судьи с ручными"""
    diffs = [abs(judge[c][k] - human[c][k]) for c in judge.keys() & human.keys() for k in JUDGE_KEYS
             if isinstance(judge[c].get(k), int) and isinstance(human[c].get(k), int)]
    return {"pairs": len(diffs), "mae": round(sum(diffs) / len(diffs), 2) if diffs else None,
            "within_1": round(sum(d <= 1 for d in diffs) / len(diffs), 3) if diffs else None}


def precision_at_k(golden: dict, ranked: list[str], k: int) -> float:
    """Считает долю полезных новостей в начале ленты"""
    return sum(golden.get(e, 0) >= 1 for e in ranked[:k]) / k if k else 0.0


def recall_at_k(golden: dict, ranked: list[str], k: int) -> float:
    """Считает долю важных новостей, попавших в начало ленты"""
    must = {e for e, g in golden.items() if g >= 2}
    return len(must & set(ranked[:k])) / len(must) if must else 1.0


def ndcg_at_k(golden: dict, ranked: list[str], k: int) -> float:
    """Оценивает порядок новостей в ленте"""
    dcg = sum((2 ** golden.get(e, 0) - 1) / math.log2(i + 2) for i, e in enumerate(ranked[:k]))
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(sorted(golden.values(), reverse=True)[:k]))
    return dcg / idcg if idcg else 0.0


def ranking_metrics(gold: dict[str, dict], ranks: dict[str, list[str]], k: int = 5) -> dict:
    """Считает метрики ленты по всем размеченным компаниям"""
    rows = [(precision_at_k(g, ranks.get(c, []), k), recall_at_k(g, ranks.get(c, []), k), ndcg_at_k(g, ranks.get(c, []), k))
            for c, g in gold.items()]

    def mean(i: int) -> float | None:
        """Считает среднее значение метрики"""
        return round(sum(x[i] for x in rows) / len(rows), 3) if rows else None

    return {f"precision@{k}": mean(0), f"recall@{k}": mean(1), f"nDCG@{k}": mean(2), "companies": len(rows)}
