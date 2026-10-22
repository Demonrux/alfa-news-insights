from __future__ import annotations

import csv
import re
from pathlib import Path

from ..domain.model import Refs
from ..domain.text import neutralize
from ..infra import llm
from ..infra.repo import RUNS, load_prompt, refs, report_text


def _norm(s: str) -> str:
    """Приводит текст к виду, удобному для поиска цитаты"""
    s = re.sub(r"[«»\"'“”„]", "", s.lower().replace("ё", "е")).replace("—", "-").replace("–", "-")
    s = re.sub(r"=== page \d+ ===", " ", re.sub(r"-\s*\n\s*", "", s))
    return re.sub(r"\s+", " ", s).strip()


def verify_quote(quote: str, text: str) -> bool:
    """Проверяет, что цитата есть в тексте отчёта"""
    return _norm(quote) in _norm(text)


def verify_registry(r: Refs | None = None) -> list[tuple[str, str]]:
    """Находит тезисы, цитат которых нет в отчётах ЦМИ"""
    r = r or refs()
    texts = {rid: report_text(rid) for rid in {t["report_id"] for t in r.registry.values()}}
    return [(tid, t["quote"]) for tid, t in r.registry.items() if not verify_quote(t["quote"], texts[t["report_id"]])]


def p3_vars(report_id: str, text: str, r: Refs) -> dict:
    """Готовит переменные P3 для части отчёта ЦМИ"""
    rep = r.reports[report_id]
    return {"report_title": rep["title_in_case"], "report_date": rep["report_date"], "report_text": neutralize(text),
            "taxonomy_block": r.taxonomy_block}


def extract_theses(report_id: str, caller: llm.Caller, max_chars: int = 24000) -> Path:
    """Достаёт новые тезисы из отчёта ЦМИ для ручной проверки"""
    r, p, text, rows = refs(), load_prompt("p3_theses"), report_text(report_id), []
    for part in (text[i:i + max_chars] for i in range(0, len(text), max_chars)):
        msgs = p.render(**p3_vars(report_id, part, r))
        obj = llm.extract_json(caller(p.meta["task"], msgs, p.meta).text)
        rows += [{**t, "quote_ok": verify_quote(t["quote"], text)} for t in obj.get("theses", [])]
    out = RUNS / f"theses_{report_id}.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["thesis_id", "report_id", "factors", "okved_hints", "direction", "thesis", "forecast", "quote",
                    "horizon", "status", "superseded_by", "quote_ok"])
        for i, t in enumerate(rows, 1):
            w.writerow([f"T-NEW-{i:02d}", report_id, ";".join(t["factors"]), ";".join(t.get("okved_hints", [])), t["direction"],
                        t["thesis"], t.get("forecast") or "", t["quote"], t["horizon"], "draft", "", t["quote_ok"]])
    return out
