from __future__ import annotations

import time

from prompts.pe.domain import checks
from prompts.pe.domain.model import Refs
from prompts.pe.infra import llm
from prompts.pe.infra.repo import load_prompt

from .trace import Trace


def _retry_messages(messages: list[dict], answer: str, errors: list[str]) -> list[dict]:
    """Добавляет к диалогу ответ модели и просьбу исправить ошибки"""
    return messages + [{"role": "assistant", "content": answer[:2000]},
                       {"role": "user", "content": "Ответ не прошёл проверку: " + "; ".join(errors)
                        + ". Верни исправленный JSON целиком, без пояснений."}]


def ask(caller: llm.Caller, prompt_id: str, variables: dict, trace: Trace, stage: str, r: Refs) -> dict | None:
    """Отправляет промпт модели и проверяет ответ по схеме, при ошибке просит исправить один раз"""
    p = load_prompt(prompt_id)
    messages = p.render(**variables)
    for attempt in (1, 2):
        t0 = time.time()
        res = caller(p.meta["task"], messages, p.meta)
        try:
            obj = llm.extract_json(res.text)
            errors = [e["fix"] for e in checks.validate_schema(obj, r.schemas[p.schema_name])[:5]]
        except llm.JSONExtractError as e:
            obj, errors = None, [str(e)]
        trace.llm(stage, p.version, res, int((time.time() - t0) * 1000), ok=not errors, attempt=attempt, errors=errors)
        if not errors:
            return obj
        messages = _retry_messages(messages, res.text or "", errors)
    return None
