from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from collections import defaultdict

from .app import evals, feed, theses
from .domain import company as co
from .domain import metrics
from .domain.text import to_json
from .infra.llm import live_caller
from .infra.repo import load_cases, load_prompt, refs


def _jsonl(pattern: str) -> list[dict]:
    """Читает все строки из файлов jsonl"""
    return [json.loads(x) for p in sorted(glob.glob(pattern)) for x in open(p, encoding="utf-8") if x.strip()]


def _csv(path: str) -> list[dict]:
    """Читает строки CSV"""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cmd_run(a) -> int:
    """Прогоняет промпт на тестовых кейсах"""
    opt = {"case": a.case, "role": a.role, "draft": a.draft, "turn": a.turn, "limit": a.limit}
    rows = evals.run_cases(a.prompt, a.cases, a.mode, a.out, opt, live_caller() if a.mode == "live" else None)
    return 0 if all(r["status"] in ("pass", "rendered") for r in rows) else 1


def cmd_render(a) -> int:
    """Показывает готовый промпт для одного кейса"""
    case = next(c for c in load_cases(a.cases) if c["id"] == a.case)
    v, _ = evals.vars_for(load_prompt(a.prompt).id, case, {"role": a.role, "draft": a.draft, "turn": a.turn}, refs())
    for m in load_prompt(a.prompt).render(**v):
        print(f"===== {m['role'].upper()} =====\n{m['content']}\n")
    return 0


def cmd_theses(a) -> int:
    """Проверяет, ищет или показывает тезисы ЦМИ"""
    if a.action == "verify":
        bad = theses.verify_registry()
        for tid, q in bad:
            print(f"НЕТ В ТЕКСТЕ: {tid}: «{q}»")
        print(f"проверено {len(refs().registry)}, не найдено {len(bad)}")
        return 1 if bad else 0
    if a.action == "extract":
        print(theses.extract_theses(a.report_id, live_caller()))
        return 0
    for t in refs().registry.values():
        if not a.factor or a.factor in t["factors"]:
            print(f"{t['thesis_id']:<10} {t['status']:<10} {t['report_date']}  {';'.join(t['factors']):<30} {t['thesis'][:90]}")
    return 0


def _grounding(rows: list[dict]) -> dict:
    """Считает, сколько карточек прошли автопроверку и какие ошибки встречались"""
    counts = defaultdict(int)
    for r in rows:
        for i in r.get("precheck_issues", []):
            counts[i.split(":")[1]] += 1
    return {"cards": len(rows), "passed_precheck": sum(r["status"] == "pass" for r in rows), "issue_counts": dict(counts)}


def _ranking(gold_path: str, ranking_path: str, k: int) -> dict:
    """Считает метрики ленты по ручной разметке"""
    gold, ranks = defaultdict(dict), defaultdict(list)
    for r in _csv(gold_path):
        gold[r["company_id"]][r["event_id"]] = int(r["relevance"])
    for r in sorted(_csv(ranking_path), key=lambda r: int(r["rank"])):
        ranks[r["company_id"]].append(r["event_id"])
    return metrics.ranking_metrics(gold, ranks, k)


def _agreement(judge_path: str, human_path: str) -> dict:
    """Сравнивает оценки судьи с ручными"""
    judge = {r["case"]: r.get("output") or {} for r in _jsonl(judge_path)}
    human = {r["case"]: {k: int(v) for k, v in r.items() if k in metrics.JUDGE_KEYS and v} for r in _csv(human_path)}
    return metrics.judge_agreement(judge, human)


METRICS = {
    "p1": lambda a: metrics.p1_metrics(_jsonl(a.paths[0]), evals.p1_expectations()),
    "judge": lambda a: metrics.judge_summary([r.get("output") for r in _jsonl(a.paths[0])]),
    "agreement": lambda a: _agreement(a.paths[0], a.paths[1]),
    "grounding": lambda a: _grounding(_jsonl(a.paths[0])),
    "ranking": lambda a: _ranking(a.paths[0], a.paths[1], a.k),
}


def cmd_metrics(a) -> int:
    """Считает метрики качества"""
    print(to_json(METRICS[a.kind](a)))
    return 0


def cmd_profile(a) -> int:
    """Показывает профиль чувствительности компании"""
    rows = {r["SYNTHETIC_U"]: r for r in _csv(a.companies)}
    print(to_json(co.sensitivity(rows[a.company_id], refs()), pretty=True))
    return 0


def cmd_examples(a) -> int:
    """Сохраняет примеры карточек"""
    for p in feed.export_examples(a.out):
        print(p)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Запускает команды комплекта"""
    ap = argparse.ArgumentParser(prog="python -m prompts.pe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "render"):
        p = sub.add_parser(name)
        p.add_argument("prompt")
        p.add_argument("cases")
        p.add_argument("--case", required=name != "run")
        p.add_argument("--role")
        p.add_argument("--draft", default="reference", choices=["reference", "bad"])
        p.add_argument("--turn", type=int, default=0)
        p.add_argument("--mode", default="dry", choices=["dry", "mock", "live"])
        p.add_argument("--limit", type=int)
        p.add_argument("--out", default="runs")
        p.set_defaults(fn={"run": cmd_run, "render": cmd_render}[name])
    t = sub.add_parser("theses")
    t.add_argument("action", choices=["verify", "extract", "list"])
    t.add_argument("report_id", nargs="?")
    t.add_argument("--factor")
    t.set_defaults(fn=cmd_theses)
    m = sub.add_parser("metrics")
    m.add_argument("kind", choices=list(METRICS))
    m.add_argument("paths", nargs="+")
    m.add_argument("--k", type=int, default=5)
    m.set_defaults(fn=cmd_metrics)
    pr = sub.add_parser("profile")
    pr.add_argument("companies")
    pr.add_argument("company_id")
    pr.set_defaults(fn=cmd_profile)
    e = sub.add_parser("examples")
    e.add_argument("--out", default="examples")
    e.set_defaults(fn=cmd_examples)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
