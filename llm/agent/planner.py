from __future__ import annotations

import hashlib

from prompts.pe.app.feed import not_relevant_text
from prompts.pe.domain import checks
from prompts.pe.domain import company as co
from prompts.pe.domain.model import Article, Refs, event_factors, primary_factor
from prompts.pe.domain.text import detect_injection, to_json, wrap_article
from prompts.pe.infra import llm

from .ask import ask
from .errors import NotRelevant, PipelineError
from .tools import Tool, gather, get_profile
from .trace import Trace

MANDATORY = ("get_profile", "search_alfa_research")


def _news_key(news: dict) -> str:
    """Считает ключ новости для кэша классификации"""
    return hashlib.sha1((news.get("title", "") + news.get("text", "")).encode("utf-8")).hexdigest()[:16]


def _event(news: dict, caller: llm.Caller, trace: Trace, r: Refs, today: str) -> dict:
    """Получает событие из P1 и проверяет его"""
    ev = ask(caller, "p1_classify", {"today": today, "articles_block": wrap_article(Article.from_dict(news)),
                                     "taxonomy_block": r.taxonomy_block}, trace, "A", r)
    errors = checks.check_event(ev, r) if ev is not None else [{"fix": "модель не вернула событие"}]
    trace.add("A", "check", "event_check", issues=[e["fix"] for e in errors])
    if errors:
        raise PipelineError("не удалось классифицировать новость", trace, issues=errors)
    return ev


def classify(news: dict, caller: llm.Caller, trace: Trace, r: Refs, today: str, cache: dict | None = None,
             event: dict | None = None) -> dict:
    """Определяет факторы новости один раз для всех компаний и отмечает попытки инъекции"""
    key = _news_key(news)
    if event is not None:
        trace.add("A", "decision", "event_provided")
        ev = event
    elif cache is not None and key in cache:
        trace.add("A", "decision", "p1_cache_hit", key=key)
        ev = cache[key]
    else:
        ev = _event(news, caller, trace, r, today)
        if cache is not None:
            cache[key] = ev
    if hits := detect_injection(news.get("title", "") + "\n" + news.get("text", "")):
        ev = dict(ev, uncertainty_flags=sorted(set(ev.get("uncertainty_flags", [])) | {"injection_suspected"}))
        trace.add("A", "check", "injection_detector", hits=hits[:5])
    if not ev["is_business_relevant"]:
        raise NotRelevant(ev.get("irrelevance_reason") or "событие не влияет на бизнес", trace, event=ev)
    return ev


def relevance(row: dict, event: dict, counterparties: list[dict], r: Refs) -> list[dict]:
    """Находит, чем новость задевает компанию через её признаки и контрагентов"""
    factors, primary, okveds = set(event_factors(event)), primary_factor(event), set(event.get("okved_hints", []))
    out = [{"kind": "okved" if it["feature"] == "MAINOKVED_CODE" else "direct", "factor": f, "feature": it["feature"],
            "effect": it["effect"], "contribution": round(it["weight"] * (1.0 if f == primary else 0.6), 2), "explanation": it["why"]}
           for f, v in co.sensitivity(row, r, event).items() if f in factors for it in v["items"]]
    out += [{"kind": "graph", "factor": primary, "direction": c["direction"], "okved": co.okved2(c.get("okved")), "share": c["share"],
             "effect": "risk", "contribution": round(float(c["share"]), 2), "explanation": ""}
            for c in counterparties or [] if co.okved2(c.get("okved")) in okveds
            and c.get("direction") in ("buyer", "supplier") and float(c.get("share") or 0) >= 0.05]
    return sorted(out, key=lambda x: -x["contribution"])


def plan_and_gather(case: dict, caller: llm.Caller, trace: Trace, r: Refs, tools: dict[str, Tool] | None = None) -> list[str]:
    """Строит план и собирает профиль компании и позицию банка"""
    if not case["components"]:
        raise NotRelevant(not_relevant_text([r.factor_names.get(f, f) for f in event_factors(case["event"])]), trace, event=case["event"])
    plan = ask(caller, "p4_planner", {"event_json": to_json(case["event"]), "portrait": get_profile({}, case),
                                      "relevance_block": co.relevance_block(case["components"], r)}, trace, "B", r)
    steps = list((plan or {}).get("steps", []))
    for name in (n for n in MANDATORY if n not in {s["tool"] for s in steps}):
        args = {"factor": primary_factor(case["event"])} if name == "search_alfa_research" else {}
        steps.append({"tool": name, "args": args, "why": "обязательный шаг"})
        trace.add("B", "decision", "mandatory_tool_added", tool=name)
    return gather(steps, case, tools, trace, "B")
