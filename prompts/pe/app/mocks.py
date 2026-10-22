from __future__ import annotations

from ..domain.metrics import JUDGE_KEYS
from ..domain.model import MACRO_FACTORS, primary_factor
from ..domain.text import to_json
from ..infra import llm


_PASS = {"grounding": 5, "personalization": 5, "not_retelling": 5, "bank_view_correct": 5, "actionability": 5}


def _as_text(answer) -> str:
    """Отдаёт готовый ответ строкой JSON"""
    return answer if isinstance(answer, str) else to_json(answer)


def _mock_p1(case: dict) -> dict:
    """Собирает событие P1 из ожиданий кейса"""
    e = case.get("expect", {})
    rel = e.get("is_business_relevant", True)
    codes = [e.get("primary_factor")] + [c for c in e.get("factors_include", []) if c != e.get("primary_factor")]
    factors = [{"code": c, "direction": e.get("direction", "unclear") if i == 0 else "unclear", "is_primary": i == 0,
                "evidence": "mock"} for i, c in enumerate(codes[:4])] if rel else []
    return {"is_business_relevant": rel, "irrelevance_reason": None if rel else "mock",
            "title": case["articles"][0]["title"][:120], "event_date": None,
            "geography": {"scope": "russia", "regions": [], "countries": []}, "factors": factors, "commodities": [],
            "okved_hints": e.get("okved_include", []), "actors": [], "key_facts": [], "horizon": "short",
            "uncertainty_flags": e.get("flags_include", [])}


def _mock_p4(case: dict) -> dict:
    """Собирает план P4 по тем же правилам, что описаны в промпте"""
    ev = case["event"]
    prim = primary_factor(ev, "KEY_RATE")
    indicator = {f: k for k, f in MACRO_FACTORS.items()}.get(prim)
    steps = [{"tool": "get_profile", "args": {}, "why": "портрет"},
             {"tool": "search_alfa_research", "args": {"factor": prim}, "why": "позиция банка"}]
    if indicator:
        steps.append({"tool": "get_macro", "args": {"indicator": indicator}, "why": "прогноз ЦМИ"})
    if ev.get("okved_hints") or any(c.get("kind") == "graph" for c in case.get("components", [])):
        steps.append({"tool": "get_counterparties", "args": {"direction": "all", "okved": ev.get("okved_hints", [])}, "why": "контрагенты"})
    return {"event_type": "macro" if indicator else "industry", "focus_factors": [prim], "steps": steps}


MOCKS = {
    "p1_classify": _mock_p1,
    "p4_planner": _mock_p4,
    "p5_interpret": lambda case: case.get("reference") or {},
    "p8_fix": lambda case: case.get("reference") or {},
    "p7_critic": lambda case: {"pass": True, "scores": _PASS, "issues": [], "need_more_data": []},
    "p13_judge": lambda case: dict.fromkeys(JUDGE_KEYS, 3) | {"factual_errors": [], "is_retelling": False, "comment": "mock"},
    "p12_chat": lambda case: {"answer": "mock", "items": [], "followups": [], "need_tool": None, "basis": "no_data"},
    "p3_theses": lambda case: {"theses": []},
}


def mock_output(prompt_id: str, case: dict) -> str:
    """Возвращает заготовленный ответ вместо модели"""
    if (m := (case.get("mock") or {}).get(prompt_id)) is not None:
        return _as_text(m)
    if prompt_id not in MOCKS:
        raise ValueError(f"нет mock для {prompt_id}")
    return to_json(MOCKS[prompt_id](case))


def mock_caller(case: dict, overrides: dict | None = None) -> llm.Caller:
    """Создаёт заглушку модели для прогонов без API"""
    def run(task: str, messages: list[dict], meta: dict) -> llm.LLMResult:
        """Отдаёт заготовленный ответ как ответ модели"""
        o = (overrides or {}).get(meta["id"])
        text = mock_output(meta["id"], case) if o is None else _as_text(o)
        tin = llm.estimate_tokens(" ".join(m["content"] for m in messages))
        return llm.LLMResult(text, "mock", tin, llm.estimate_tokens(text), 0.0, 0.0)

    return run
