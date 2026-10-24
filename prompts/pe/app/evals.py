from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from ..domain import checks
from ..domain.metrics import p1_metrics
from ..domain.model import Article, Refs, event_factors, primary_factor
from ..domain.text import neutralize, to_json, wrap_article
from ..infra import llm
from ..infra.repo import CASES, load_cases, load_prompt, refs, report_text
from .context import build_context, review_vars
from .feed import digest_vars
from .mocks import mock_output
from .theses import p3_vars, verify_quote


P5_CASES = CASES / "p5_cases.yaml"


def draft_of(case: dict, which: str = "reference") -> dict:
    """Берёт эталонный или плохой черновик из кейса"""
    if which == "bad" and case.get("bad_draft"):
        return case["bad_draft"]
    return case.get("reference") or case.get("bad_draft") or {}


def vars_for(prompt_id: str, case: dict, opt: dict, r: Refs):
    """Готовит переменные промпта для тестового кейса"""
    if prompt_id == "p1_classify":
        arts = "\n\n".join(wrap_article(Article.from_dict(a)) for a in case["articles"])
        return {"today": case.get("today", ""), "articles_block": arts, "taxonomy_block": r.taxonomy_block}, None
    if prompt_id == "p3_theses":
        text = report_text(case["report_id"])[: case.get("max_chars") or None]
        return p3_vars(case["report_id"], text, r), text
    role = opt.get("role") or case.get("role", "cfo")
    if prompt_id == "p14_digest":
        src = {c["id"]: c for c in load_cases(P5_CASES)}
        cards = [{"card_id": c["card_id"], "company": c.get("company", "—"), "insight": src[c["from_case"]]["reference"]}
                 for c in case["cards"]]
        return digest_vars(cards, role, case.get("period", "week"), case.get("today", ""), r), cards
    ctx = build_context(case, role, r)
    draft = draft_of(case, opt.get("draft", "reference"))
    v = review_vars(ctx.vars, draft, checks.precheck(draft, ctx, r)["issues"])
    chat = case.get("chat") or [{"question": "Откуда эти цифры?"}]
    turn = chat[min(opt.get("turn", 0), len(chat) - 1)]
    v["history_block"] = "\n".join(f"{h['role']}: {h['text']}" for h in turn.get("history", [])) or "—"
    v["question"] = neutralize(turn["question"])
    return v, ctx


def _missing(expected: list, actual: list, message: str) -> list[str]:
    """Перечисляет ожидаемые значения, которых нет в ответе"""
    return [f"{message} {x}" for x in expected if x not in actual]


def _check_p1(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Сверяет ответ P1 с ожиданиями кейса"""
    exp, fails = case.get("expect", {}), [f"schema: {i['fix']}" for i in checks.check_event(obj, r)]
    if fails:
        return fails, {}
    codes, prim = event_factors(obj), primary_factor(obj)
    if "is_business_relevant" in exp and obj["is_business_relevant"] != exp["is_business_relevant"]:
        fails.append(f"is_business_relevant={obj['is_business_relevant']}, ожидалось {exp['is_business_relevant']}")
    if exp.get("primary_factor") and prim not in [exp["primary_factor"], *exp.get("primary_alternatives", [])]:
        fails.append(f"основной фактор {prim}, ожидался {exp['primary_factor']}")
    fails += _missing(exp.get("factors_include", []), codes, "нет фактора")
    fails += [f"лишний фактор {c}" for c in exp.get("factors_exclude", []) if c in codes]
    fails += _missing(exp.get("okved_include", []), obj["okved_hints"], "нет ОКВЭД")
    fails += _missing(exp.get("flags_include", []), obj["uncertainty_flags"], "нет флага")
    if exp.get("no_confirmed_facts") and any(k["status"] == "confirmed" for k in obj["key_facts"]):
        fails.append("слухи помечены как confirmed")
    return fails, {"primary": prim, "factors": codes}


def _check_card(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Сверяет карточку с ожиданиями кейса"""
    exp, pre = case.get("expect", {}), checks.precheck(obj, ctx, r)
    fails = [f"{checks.tag(i)}[{i['item_index']}] {i['fix']}" for i in checks.with_severity(pre["issues"], "blocker", "major")]
    if exp.get("must_cite_any") and not {b["thesis_id"] for b in obj.get("bank_view", [])} & set(exp["must_cite_any"]):
        fails.append(f"не процитирован ни один из тезисов {exp['must_cite_any']}")
    fails += _missing(exp.get("must_offer_rule", []), [a.get("rule_id") for a in obj.get("actions", [])], "нет действия по правилу")
    products = [a.get("product") for a in obj.get("actions", [])]
    fails += [f"предложен лишний продукт {x}" for x in exp.get("must_not_offer_product", []) if x in products]
    if exp.get("overall_impact") and obj.get("overall_impact") not in exp["overall_impact"]:
        fails.append(f"overall_impact={obj.get('overall_impact')}, ожидалось одно из {exp['overall_impact']}")
    return fails, {"precheck_issues": [checks.tag(i) for i in pre["issues"]]}


def _check_critic(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Сверяет итог критика с ожиданиями кейса"""
    which = opt.get("draft", "reference")
    verdict = checks.merge_verdicts(checks.precheck(draft_of(case, which), ctx, r), obj)
    ec = case.get("expect_critic", {}).get(which, {})
    fails = [f"итоговый pass={verdict['pass']}, ожидалось {ec['pass']}"] if "pass" in ec and verdict["pass"] != ec["pass"] else []
    fails += _missing(ec.get("types_include", []), [i["type"] for i in verdict["issues"]], "критик не нашёл")
    return fails, {"final_pass": verdict["pass"]}


def _check_plan(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Проверяет, что в плане есть обязательные инструменты"""
    need = ["get_profile", "search_alfa_research", *case.get("expect_plan", {}).get("tools_include", [])]
    return _missing(need, [s["tool"] for s in obj["steps"]], "в плане нет"), {}


def _check_chat(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Проверяет, что чат ссылается только на известные источники"""
    return [f"чат сослался на несуществующее {bad}" for it in obj.get("items", [])
            if (bad := [x for x in it["source_ids"] if x not in ctx.catalog])], {}


def _check_theses(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Проверяет, что цитаты новых тезисов есть в отчёте"""
    bad = [t["quote"] for t in obj.get("theses", []) if not verify_quote(t["quote"], ctx)]
    return [f"цитаты нет в отчёте: «{q[:80]}»" for q in bad], {"quotes_ok": f"{len(obj.get('theses', [])) - len(bad)}/{len(obj.get('theses', []))}"}


def _check_digest(obj: dict, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Проверяет сводку P14"""
    return [f"{i['type']}: {i['fix']}" for i in checks.check_digest(obj, ctx, r)], {}


CHECKS = {"p1_classify": _check_p1, "p5_interpret": _check_card, "p8_fix": _check_card, "p14_digest": _check_digest,
          "p7_critic": _check_critic, "p4_planner": _check_plan, "p12_chat": _check_chat, "p3_theses": _check_theses}


SELF_VALIDATING = {"p1_classify", "p5_interpret", "p8_fix", "p14_digest"}


def check_output(prompt_id: str, obj, case: dict, ctx, opt: dict, r: Refs) -> tuple[list[str], dict]:
    """Находит ошибки в ответе модели"""
    fails, extra = [], {}
    if prompt_id not in SELF_VALIDATING:
        fails = [f"schema: {i['fix']}" for i in checks.validate_schema(obj, r.schemas[load_prompt(prompt_id).schema_name])]
    if not fails and prompt_id in CHECKS:
        fails, extra = CHECKS[prompt_id](obj, case, ctx, opt, r)
    blob = to_json(obj).lower()
    fails += [f"в ответе есть запрещённое «{s}»" for s in case.get("expect", {}).get("must_not_contain", []) if s.lower() in blob]
    return fails, extra


def run_cases(prompt_id: str, cases_path: str, mode: str = "dry", out_dir: str = "runs", opt: dict | None = None,
              caller: llm.Caller | None = None) -> list[dict]:
    """Прогоняет промпт на всех кейсах и сохраняет отчёт"""
    opt, r, p = opt or {}, refs(), load_prompt(prompt_id)
    cases = [c for c in load_cases(cases_path) if not opt.get("case") or c["id"] in opt["case"].split(",")][: opt.get("limit")]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f"{p.id}_{mode}_{datetime.now():%Y%m%d_%H%M%S}"
    rows = []
    with stem.with_suffix(".jsonl").open("w", encoding="utf-8") as fo:
        for case in cases:
            v, ctx = vars_for(p.id, case, opt, r)
            messages = p.render(**v)
            row = {"case": case["id"], "prompt": p.version, "mode": mode, "status": "rendered", "fails": [],
                   "tokens_in": llm.estimate_tokens("\n".join(m["content"] for m in messages))}
            raw = obj = None
            if mode != "dry":
                t0 = time.time()
                try:
                    if mode == "mock":
                        raw = mock_output(p.id, case)
                    else:
                        result = caller(p.meta["task"], messages, p.meta)
                        raw = result.text
                        row.update(finish_reason=result.finish_reason, model=result.model,
                                   tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                                   cost_rub=result.cost_rub,
                                   request_max_tokens=result.request_max_tokens,
                                   response_message_keys=result.response_message_keys,
                                   response_content_type=result.response_content_type,
                                   response_content_chars=result.response_content_chars,
                                   reasoning_chars=result.reasoning_chars,
                                   usage_completion_details=result.usage_completion_details)
                    obj = llm.extract_json(raw)
                    row["fails"], extra = check_output(p.id, obj, case, ctx, opt, r)
                    row.update(extra)
                except (llm.JSONExtractError, RuntimeError) as e:
                    row["fails"].append(f"{type(e).__name__}: {e}")
                row.update(latency_s=round(time.time() - t0, 2), status="fail" if row["fails"] else "pass")
            rows.append(row)
            fo.write(to_json({**row, "raw": raw, "output": obj}) + "\n")
            print(f"{row['status']:<9} {case['id']:<34} in≈{row['tokens_in']:>5}  {'; '.join(row['fails'])[:150]}")
    summary = summarize(p.id, rows)
    stem.with_suffix(".md").write_text(summary, encoding="utf-8")
    print("\n" + summary)
    return rows


def p1_expectations() -> dict[str, dict]:
    """Читает ожидания кейсов P1"""
    return {c["id"]: c.get("expect", {}) for c in load_cases(CASES / "p1_cases.yaml")}


def summarize(prompt_id: str, rows: list[dict]) -> str:
    """Пишет краткий отчёт о прогоне"""
    n = len(rows)
    lines = [f"# {prompt_id}: {sum(x['status'] == 'pass' for x in rows)}/{n} кейсов прошли", "",
             f"- Токены на вход: всего ≈ {sum(x['tokens_in'] for x in rows)}, на кейс ≈ {sum(x['tokens_in'] for x in rows) // max(n, 1)}"]
    if prompt_id == "p1_classify" and any(x.get("primary") for x in rows):
        lines.append("- " + ", ".join(f"{k}: {v}" for k, v in p1_metrics(rows, p1_expectations()).items()))
    if fails := [x for x in rows if x["status"] == "fail"]:
        lines += ["", "## Провалы", ""] + [f"- **{x['case']}**: " + "; ".join(x["fails"]) for x in fails]
    return "\n".join(lines) + "\n"
