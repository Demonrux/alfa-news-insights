import argparse
import sys

from prompts.pe.domain.text import to_json
from prompts.pe.infra.llm import live_caller
from prompts.pe.infra.repo import load_cases

from .demo import run_case
from .errors import PipelineError
from .trace import Trace


def main(argv: list[str] | None = None) -> int:
    """Прогоняет агента на одном тестовом кейсе и печатает карточку и трейс"""
    ap = argparse.ArgumentParser(prog="python -m llm.agent")
    ap.add_argument("cases")
    ap.add_argument("--case", required=True)
    ap.add_argument("--mode", default="mock", choices=["mock", "live"])
    ap.add_argument("--role")
    ap.add_argument("--trace-dir")
    a = ap.parse_args(argv)
    case = next(c for c in load_cases(a.cases) if c["id"] == a.case)
    trace, code = Trace(), 0
    try:
        card, _ = run_case(case, live_caller() if a.mode == "live" else None, role=a.role, trace=trace)
    except PipelineError as e:
        card, code = {"error": str(e), **{k: v for k, v in e.details.items() if k != "event"}}, 1
    trace.save(a.trace_dir)
    print(to_json({"card": card, "trace": trace.to_dict()}, pretty=True))
    return code


sys.exit(main())
