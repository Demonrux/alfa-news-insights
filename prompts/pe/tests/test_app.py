import json

import pytest
from jsonschema import Draft202012Validator

from prompts.pe.app.context import allowed_actions, build_context, select_theses
from prompts.pe.app.feed import export_examples
from prompts.pe.app.theses import verify_registry
from prompts.pe.cli import main
from prompts.pe.domain.checks import check_digest
from prompts.pe.infra import llm
from prompts.pe.infra.repo import CASES as CASES_DIR, MODELS_FILE, PROMPTS, ROOT, load_prompt, load_yaml
from prompts.pe.tests.data import CASES, FIRST, R, ROLES

PROMPT_IDS = ["p1_classify", "p3_theses", "p4_planner", "p5_interpret", "p7_critic", "p8_fix", "p12_chat", "p13_judge", "p14_digest"]


def test_registry_quotes_ids_and_statuses():
    assert verify_registry() == []
    for tid, t in R.registry.items():
        assert t["report_id"] in R.reports and t["factors"] and set(t["factors"]) <= set(R.factor_codes), tid
        if t["status"] == "superseded":
            assert R.registry[t["superseded_by"]]["status"] == "current", tid
    stale = {k for k, v in R.reports.items() if v["status"] == "stale"}
    assert stale == {"R_STEEL"} and all(t["status"] == "stale" for t in R.registry.values() if t["report_id"] in stale)


def test_select_theses_only_current():
    ev = {"factors": [{"code": "KEY_RATE", "is_primary": True}, {"code": "COMMODITIES", "is_primary": False}], "okved_hints": ["24"]}
    got = select_theses(ev, {"MAINOKVED_CODE": "24.10"}, R, max_n=20)
    ids = {t["thesis_id"] for t in got}
    assert got and all(t["status"] == "current" for t in got) and not ids & {"T-STL-01", "T-CONS-06"}
    assert got[0]["factors"][0] == "KEY_RATE"


@pytest.mark.parametrize("name", sorted(R.schemas))
def test_schemas_are_valid(name):
    Draft202012Validator.check_schema(R.schemas[name])


@pytest.mark.parametrize("pid", PROMPT_IDS)
def test_prompt_metadata_and_untrusted_rule(pid):
    p = load_prompt(pid)
    assert p.meta["task"] and p.inputs and p.meta["schema"].removesuffix(".json") in R.schemas
    assert '{% include "zero_trust.j2" %}' in p.system and "<news" not in p.system + p.user


def test_blocks_and_render_errors():
    assert all(len(R.role_block(x)) > 50 for x in ROLES) and "Стиль" in R.style and "KEY_RATE" in R.taxonomy_block
    with pytest.raises(KeyError):
        load_prompt("p5_interpret").render(today="x")


def test_p5_family_renders_for_every_case():
    extra = {"draft_json": "{}", "insight_json": "{}", "precheck_block": "[]", "issues_json": "[]", "new_materials_block": "",
             "history_block": "—", "question": "?"}
    for case in CASES.values():
        v = build_context(case).vars
        for pid in ("p4_planner", "p5_interpret", "p7_critic", "p8_fix", "p12_chat", "p13_judge"):
            load_prompt(pid).render(**v, **extra)


def test_actions_rules_and_disclaimers():
    company = {"CL_PRODUCT_LOA_MARK": 1, "CL_PRODUCT_DEP_MARK": 1}
    assert {x["id"] for x in allowed_actions(["KEY_RATE"], company, "treasurer", R)} == {"A-RATE-DEBT", "A-RATE-DEP"}
    assert allowed_actions(["KEY_RATE"], company, "chief_accountant", R) == []
    assert len({x["id"] for x in R.actions}) == len(R.actions)
    for x in R.actions:
        assert x["when"]["factor"] in R.factor_codes and x["when"]["feature"] in R.features["flags"]
        assert set(x.get("roles", [])) <= set(ROLES) and (x["product"] is None) == (x.get("cta") is None)
    basis = set(R.schemas["insight"]["properties"]["source_basis"]["enum"]) | set(R.schemas["chat"]["properties"]["basis"]["enum"])
    assert basis <= set(R.disclaimers["by_basis"])


def test_catalog_contains_only_what_was_given():
    ctx = build_context(FIRST)
    assert {"news:s001", "T-RATE-02", "cp:buyers_68", "cp:group"} <= set(ctx.catalog) and "T-RATE-07" not in ctx.catalog
    assert "крупный бизнес" in ctx.vars["portrait"]


@pytest.mark.parametrize("raw", ['{"a": 1}', '<think>x</think>\n{"a": 1}', 'Ответ:\n```json\n{"a": 1}\n```',
                                 'Ответ: {"a": 1,} спасибо', '{"a": "скобка } внутри", "b": 1}'])
def test_extract_json_variants(raw):
    assert llm.extract_json(raw)["a"] in (1, "скобка } внутри")


def test_extract_json_truncated():
    with pytest.raises(llm.JSONExtractError, match="обрезан"):
        llm.extract_json('{"a": [1, 2')


def test_journal_stops_at_daily_budget(tmp_path):
    j = llm.Journal(tmp_path / "j.jsonl", limit_rub=1.0)
    j.write(llm.LLMResult("x", "m", 10, 10, 0.1, 0.6), "p5_interpret@v2", "interpret")
    j.check()
    j.write(llm.LLMResult("x", "m", 10, 10, 0.1, 0.6), "p5_interpret@v2", "interpret")
    with pytest.raises(llm.BudgetExceeded):
        j.check()
    assert json.loads((tmp_path / "j.jsonl").read_text().splitlines()[0])["prompt"] == "p5_interpret@v2"


def test_digest_check():
    cards = [{"card_id": "card:a", "insight": FIRST["reference"]}]
    ok = {"title": "Деньги остаются дорогими", "period": "week", "summary": "Ставка сохранится на уровне 14% до конца года.",
          "top": [{"card_id": "card:a", "why_now": "-"}],
          "watch": [{"what": "ЦБ", "when": "23 октября", "why": "-", "source_ids": ["T-RATE-02"]}], "role": "cfo"}
    assert check_digest(ok, cards, R) == []
    ok["top"][0]["card_id"], ok["watch"][0]["source_ids"] = "card:zzz", ["T-RATE-07"]
    assert len(check_digest(ok, cards, R)) == 2


def test_examples_for_front_and_back(tmp_path):
    paths = export_examples(tmp_path)
    assert len(paths) == len(CASES) + 1 and "ui" in json.loads(paths[1].read_text(encoding="utf-8"))
    assert set(json.loads(paths[0].read_text(encoding="utf-8"))) == set(ROLES)


def test_all_audience_roles_are_covered():
    assert len(ROLES) == 7
    for name in ("insight", "digest"):
        assert set(R.schemas[name]["properties"]["role"]["enum"]) == set(ROLES)
    assert R.role_block("c_level", "коммерческий директор").endswith("Должность пользователя: коммерческий директор.")


def test_one_company_different_users_get_different_cards():
    case = dict(FIRST, user_title="коммерческий директор")
    by_role = {x: build_context(case, x) for x in ROLES}
    assert len({c.vars["role_block"] for c in by_role.values()}) == len(ROLES)
    assert "коммерческий директор" in by_role["c_level"].vars["role_block"]
    company = {"FTS_FLAG": 1, "CL_PRODUCT_LOA_MARK": 1}
    assert allowed_actions(["SANCTIONS_TRADE"], company, "c_level", R)
    assert allowed_actions(["SANCTIONS_TRADE", "KEY_RATE", "FX"], company, "other", R) == []


RUNS = [("p1_classify", "p1_cases.yaml", []), ("p1_classify", "injection_cases.yaml", []), ("p4_planner", "p5_cases.yaml", []),
        ("p5_interpret", "p5_cases.yaml", []), ("p8_fix", "p5_cases.yaml", ["--draft", "bad"]),
        ("p7_critic", "p5_cases.yaml", ["--draft", "bad"]), ("p7_critic", "p5_cases.yaml", []),
        ("p12_chat", "p5_cases.yaml", []), ("p13_judge", "p5_cases.yaml", []), ("p14_digest", "digest_cases.yaml", [])]


@pytest.mark.parametrize("mode", ["dry", "mock"])
@pytest.mark.parametrize("prompt,cases,extra", RUNS)
def test_cli_run_modes(tmp_path, prompt, cases, extra, mode):
    assert main(["run", prompt, str(CASES_DIR / cases), "--mode", mode, "--out", str(tmp_path), *extra]) == 0


def test_cli_p3_dry_and_theses_verify(tmp_path):
    (tmp_path / "c.yaml").write_text("cases:\n  - {id: rate, report_id: R_RATE}\n", encoding="utf-8")
    assert main(["run", "p3_theses", str(tmp_path / "c.yaml"), "--out", str(tmp_path)]) == 0
    assert main(["theses", "verify"]) == 0


def test_paths_can_be_moved_by_environment(tmp_path):
    import subprocess, sys
    code = "from prompts.pe.infra.repo import PROMPTS, RUNS; print(PROMPTS, RUNS)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT,
                         env={"PE_PROMPTS_DIR": str(PROMPTS), "PE_RUNS_DIR": str(tmp_path), "PATH": ""}).stdout
    assert str(tmp_path) in out


def test_models_cover_every_prompt_task():
    m = load_yaml(MODELS_FILE)
    assert {load_prompt(p).meta["task"] for p in PROMPT_IDS} <= set(m) and set(m["fallback"]) <= set(m)
