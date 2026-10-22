from __future__ import annotations

from datetime import date

from prompts.pe.app.context import build_context, review_vars
from prompts.pe.domain import checks
from prompts.pe.domain import company as co
from prompts.pe.domain.model import Context, NotEligible, Refs
from prompts.pe.infra import llm
from prompts.pe.infra.repo import refs

from .ask import ask
from .errors import InsightRejected
from .planner import classify, plan_and_gather, relevance
from .tools import Tool, gather
from .trace import Trace

MAX_FIX = 2


def review(ctx: Context, caller: llm.Caller, trace: Trace, r: Refs, materials: list[str],
           tools: dict[str, Tool] | None) -> tuple[dict | None, dict]:
    """Пишет карточку, проверяет её критиком и исправляет не больше двух раз"""
    draft = ask(caller, "p5_interpret", ctx.vars, trace, "C", r)
    verdict: dict = {}
    for attempt in range(MAX_FIX + 1):
        pre = checks.precheck(draft, ctx, r, None if draft else "модель не вернула валидный JSON")
        trace.add("D", "check", "precheck", iteration=attempt, passed=pre["pass"],
                  issues=[checks.tag(i) for i in pre["issues"]])
        critic = None
        if draft is not None and not checks.with_severity(pre["issues"], "blocker"):
            critic = ask(caller, "p7_critic", review_vars(ctx.vars, draft, pre["issues"]), trace, "D", r)
        verdict = checks.merge_verdicts(pre, critic)
        trace.add("D", "decision", "verdict", iteration=attempt, passed=verdict["pass"], scores=verdict.get("scores"),
                  issues=[checks.tag(i, field=False) for i in verdict["issues"]])
        if verdict["pass"] or attempt == MAX_FIX:
            break
        materials += gather(verdict.get("need_more_data", []), ctx.case, tools, trace, "D")
        fix_vars = review_vars(ctx.vars, draft, verdict["issues"], "\n".join(materials))
        draft = ask(caller, "p8_fix", fix_vars, trace, "D", r) or draft
    return draft, verdict


def _new_case(company_data: dict, news_item: dict, role: str, user_title: str | None, today: str | None,
              trace: Trace, r: Refs) -> dict:
    """Готовит кейс из входа API и отсекает компании, которые не являются клиентами"""
    row = company_data.get("company", company_data)
    if co.is_active_client(row, r) is False:
        trace.add("A", "decision", "not_eligible", cl_type=row.get("CL_TYPE"))
        raise NotEligible(f"CL_TYPE={row.get('CL_TYPE')}: сервис только для действующих клиентов")
    return {"today": today or date.today().isoformat(), "role": role, "articles": [news_item], "company": row,
            "user_title": user_title or company_data.get("user_title"), "group": company_data.get("group"),
            "counterparties": company_data.get("counterparties") or [], "components": company_data.get("components")}


def _finish(draft: dict | None, verdict: dict, ctx: Context, trace: Trace, r: Refs) -> dict:
    """Ставит бейдж и дисклеймер и пропускает карточку только без блокирующих ошибок"""
    card = checks.finalize_card(draft, ctx.role, r) if draft else None
    problems = (checks.api_errors(card, r) if card else [{"fix": "нет карточки"}]) + checks.with_severity(verdict.get("issues", []), "blocker")
    if problems:
        trace.add("F", "decision", "rejected", errors=[e["fix"] for e in problems][:10])
        raise InsightRejected("карточка не прошла проверки", trace, issues=problems)
    trace.add("F", "decision", "accepted", critic_pass=verdict["pass"], source_basis=card["source_basis"],
              badge=card["badge"], remaining=[checks.tag(i, field=False) for i in verdict["issues"]], **checks.grounding(card, ctx))
    return card


def run_insight_pipeline(company_data: dict, news_item: dict, *, role: str | None = None, user_title: str | None = None,
                         today: str | None = None, caller: llm.Caller | None = None, tools: dict[str, Tool] | None = None,
                         trace: Trace | None = None, cache: dict | None = None, event: dict | None = None) -> dict:
    """Делает из новости и данных компании готовую карточку для API"""
    r, trace, caller = refs(), trace or Trace(), caller or llm.live_caller()
    role = role or company_data.get("role") or "cfo"
    case = _new_case(company_data, news_item, role, user_title, today, trace, r)
    try:
        case["event"] = classify(news_item, caller, trace, r, case["today"], cache, event)
        case["components"] = case["components"] or relevance(case["company"], case["event"], case["counterparties"], r)
        trace.add("B", "check", "relevance", components=[f"{c['kind']}:{c['factor']}:{c['contribution']}" for c in case["components"]])
        materials = plan_and_gather(case, caller, trace, r, tools)
        ctx = build_context(case, role, r)
        trace.add("B", "check", "context", theses=[t["thesis_id"] for t in ctx.theses], refs=len(ctx.catalog),
                  allowed_products=[a["id"] for a in ctx.allowed_actions], injection_hits=len(ctx.injection_hits))
        draft, verdict = review(ctx, caller, trace, r, materials, tools)
        return _finish(draft, verdict, ctx, trace, r)
    finally:
        trace.save()
