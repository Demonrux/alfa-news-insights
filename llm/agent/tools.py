from __future__ import annotations

import time
from typing import Callable

from prompts.pe.app.context import render_counterparties, render_portrait, select_theses, theses_block
from prompts.pe.domain.model import MACRO_FACTORS
from prompts.pe.domain.text import to_json
from prompts.pe.infra.repo import refs

from .trace import Trace

Tool = Callable[[dict, dict], str]


def _add_theses(case: dict, ids: list[str]) -> None:
    """Добавляет тезисы в контекст карточки без повторов"""
    case["theses"] = list(dict.fromkeys((case.get("theses") or []) + ids))


def get_profile(args: dict, case: dict) -> str:
    """Возвращает портрет компании без идентификаторов и точных сумм"""
    return render_portrait(case["company"], case.get("group"), refs())


def get_counterparties(args: dict, case: dict) -> str:
    """Возвращает контрагентов компании по отраслям с долями"""
    return render_counterparties(case.get("counterparties") or [], refs())


def get_event(args: dict, case: dict) -> str:
    """Возвращает событие, найденное на первом шаге"""
    return to_json(case["event"])


def search_alfa_research(args: dict, case: dict) -> str:
    """Подбирает актуальные тезисы ЦМИ по событию и по фактору из плана"""
    r, ev = refs(), case["event"]
    if args.get("factor") in r.factor_codes:
        ev = dict(ev, factors=[{"code": args["factor"], "is_primary": True}] + [f for f in ev["factors"] if f["code"] != args["factor"]])
    found = select_theses(case["event"], case["company"], r) + select_theses(ev, case["company"], r)
    _add_theses(case, [t["thesis_id"] for t in found])
    return theses_block(found)


def get_macro(args: dict, case: dict) -> str:
    """Подбирает прогнозы ЦМИ по ставке, инфляции, курсу, бюджету или ВВП"""
    factor = MACRO_FACTORS.get(str(args.get("indicator", "")).lower())
    return search_alfa_research({"factor": factor}, case) if factor else "Показатель не поддерживается."


def fixed_research(thesis_ids: list[str]) -> Tool:
    """Создаёт поиск тезисов, который отдаёт заранее выбранный список"""
    def tool(args: dict, case: dict) -> str:
        """Кладёт выбранные тезисы в контекст карточки"""
        _add_theses(case, thesis_ids)
        r = refs()
        return theses_block([r.registry[t] for t in thesis_ids if t in r.registry])
    return tool


LOCAL_TOOLS: dict[str, Tool] = {f.__name__: f for f in (get_profile, get_counterparties, get_event, search_alfa_research, get_macro)}


def run_tool(name: str, args: dict, case: dict, tools: dict[str, Tool] | None, trace: Trace, stage: str, reason: str) -> str | None:
    """Вызывает инструмент агента, внешний важнее встроенного, и пишет вызов в трейс"""
    fn = {**LOCAL_TOOLS, **(tools or {})}.get(name)
    if fn is None:
        trace.add(stage, "tool", name, args=args, reason=reason, skipped="инструмент не подключён")
        return None
    t0 = time.time()
    res = fn(args, case)
    trace.tool(stage, name, args, res, reason, int((time.time() - t0) * 1000))
    return res


def gather(steps: list[dict], case: dict, tools: dict[str, Tool] | None, trace: Trace, stage: str) -> list[str]:
    """Выполняет шаги плана и собирает их результаты как материалы"""
    results = ((s["tool"], run_tool(s["tool"], s.get("args", {}), case, tools, trace, stage, s.get("why", ""))) for s in steps)
    return [f"[{name}] {res}" for name, res in results if res]
