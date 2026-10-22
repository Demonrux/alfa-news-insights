from __future__ import annotations

from prompts.pe.app.mocks import mock_caller
from prompts.pe.infra import llm

from .loop import run_insight_pipeline
from .tools import fixed_research
from .trace import Trace


def run_case(case: dict, caller: llm.Caller | None = None, overrides: dict | None = None, role: str | None = None,
             trace: Trace | None = None) -> tuple[dict, Trace]:
    """Прогоняет пайплайн на тестовом кейсе с заглушкой модели или настоящей моделью"""
    trace = trace or Trace()
    caller = caller or mock_caller(case, {"p1_classify": case.get("event"), **(overrides or {})})
    company = {k: case.get(k) for k in ("company", "group", "counterparties", "components", "user_title")}
    tools = {"search_alfa_research": fixed_research(case["theses"])} if case.get("theses") else None
    card = run_insight_pipeline(company, case["articles"][0], role=role or case.get("role"), today=case.get("today"),
                                caller=caller, tools=tools, trace=trace)
    return card, trace
