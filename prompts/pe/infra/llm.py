from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv
from jsonschema import Draft202012Validator

from ..domain.text import to_json
from .repo import MODELS_FILE, ROOT, RUNS, refs

load_dotenv(ROOT / ".env")

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


class JSONExtractError(ValueError):
    """Ответ модели не удалось прочитать как JSON"""


class BudgetExceeded(RuntimeError):
    """Дневной лимит расходов на модели исчерпан"""


@dataclass
class LLMResult:
    """Ответ модели с токенами и стоимостью"""

    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_s: float
    cost_rub: float | None = None
    finish_reason: str | None = None
    request_max_tokens: int | None = None
    response_message_keys: list[str] | None = None
    response_content_type: str | None = None
    response_content_chars: int | None = None
    reasoning_chars: int = 0
    usage_completion_details: dict | None = None


Caller = Callable[[str, list, dict], "LLMResult"]


def _budget_day() -> str:
    """Budget day in Moscow time; the organizer resets the shared key at 03:00."""
    return (datetime.now(ZoneInfo("Europe/Moscow")) - timedelta(hours=3)).date().isoformat()


def models() -> dict:
    """Читает, какая модель отвечает за какую задачу"""
    return yaml.safe_load(MODELS_FILE.read_text(encoding="utf-8")) or {}


def model_for(task: str) -> str:
    """Возвращает модель для задачи"""
    m = models()
    if task not in m:
        raise KeyError(f"нет модели для задачи {task!r} в models.yaml")
    return m[task]


def fallback_for(task: str) -> str | None:
    """Возвращает запасную модель для задачи"""
    return (models().get("fallback") or {}).get(task)


def estimate_tokens(text: str) -> int:
    """Примерно считает токены в тексте"""
    return max(1, len(text) // 3)


def price(model: str, tokens_in: int, tokens_out: int) -> float | None:
    """Считает стоимость вызова в рублях"""
    p = (models().get("prices") or {}).get(model)
    return round(tokens_in / 1000 * p[0] + tokens_out / 1000 * p[1], 4) if p else None


class Journal:
    """Журнал вызовов моделей и дневной лимит расходов"""

    def __init__(self, path: str | Path = RUNS / "llm_journal.jsonl", limit_rub: float = 500.0):
        """Задаёт файл журнала и лимит в рублях"""
        self.path, self.limit = Path(path), limit_rub

    def spent_today(self) -> float | None:
        """Return known spend, or None if any call lacks configured model prices."""
        if not self.path.exists():
            return 0.0
        today = _budget_day()
        rows = (json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip())
        todays_rows = [row for row in rows if row.get("day") == today]
        if any(row.get("cost_rub") is None for row in todays_rows):
            return None
        return round(sum(float(row["cost_rub"]) for row in todays_rows), 4)

    def check(self) -> None:
        """Останавливает работу, если лимит исчерпан"""
        spent = self.spent_today()
        # The organizer API enforces the real shared limit. Without published
        # rates this local journal cannot calculate spend and must not treat it as 0.
        if spent is not None and spent >= self.limit:
            raise BudgetExceeded(f"лимит {self.limit} руб. в день исчерпан")

    def write(self, res: LLMResult, prompt_version: str, task: str) -> None:
        """Записывает вызов в журнал"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {"day": _budget_day(), "prompt": prompt_version, "task": task,
               **{k: v for k, v in asdict(res).items() if k != "text"}}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(to_json(row) + "\n")


def _usable_response(result: LLMResult, meta: dict) -> bool:
    """Requires a non-empty JSON object and validates it against the prompt schema."""
    try:
        parsed = extract_json(result.text)
    except JSONExtractError:
        return False
    if not isinstance(parsed, dict) or not parsed:
        return False
    schema_name = str(meta.get("schema", "")).removesuffix(".json")
    schema = refs().schemas.get(schema_name) if schema_name else None
    return not schema or Draft202012Validator(schema).is_valid(parsed)


def live_caller(journal: Journal | None = None) -> Caller:
    """Создаёт вызов настоящих моделей с журналом и лимитом"""
    journal = journal or Journal()

    def run(task: str, messages: list[dict], meta: dict) -> LLMResult:
        """Вызывает модель для одного промпта"""
        journal.check()
        kw = {"temperature": meta.get("temperature", 0.2), "max_tokens": meta.get("max_tokens", 1500)}
        model = model_for(task)
        try:
            res = call(messages, model=model, **kw)
        except BudgetExceeded:
            raise
        except RuntimeError:
            if not (fb := fallback_for(task)) or fb == model:
                raise
            journal.check()
            res = call(messages, model=fb, **kw)
            journal.write(res, f"{meta['id']}@v{meta.get('version', 0)}", task)
            return res

        # Record every successful HTTP response, even if its body is unusable.
        journal.write(res, f"{meta['id']}@v{meta.get('version', 0)}", task)
        if _usable_response(res, meta):
            return res

        fb = fallback_for(task)
        if not fb or fb == model:
            return res
        journal.check()
        fallback_result = call(messages, model=fb, **kw)
        journal.write(fallback_result, f"{meta['id']}@v{meta.get('version', 0)}", task)
        # Keep the primary response when fallback is also empty or schema-invalid.
        # This preserves the more useful diagnostics and avoids replacing a partial
        # JSON answer with an empty response (for example finish_reason="length").
        return fallback_result if _usable_response(fallback_result, meta) else res

    return run


def call(messages: list[dict], model: str, temperature: float = 0.2, max_tokens: int = 1500) -> LLMResult:
    """Отправляет запрос модели; таймауты не повторяются, чтобы не дублировать платный запрос."""
    base = (os.environ.get("LLM_API_BASE") or os.environ.get("LLM_BASE_URL")
            or "https://changellenge.up.railway.app/v1")
    key = os.environ.get("LLM_API_KEY")
    if not base or not key:
        raise RuntimeError("задайте LLM_API_BASE и LLM_API_KEY или используйте --mode dry/mock")
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}}
    last = None
    for attempt in range(3):
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=float(os.environ.get("LLM_TIMEOUT", "120"))) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage") or {}
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content")
            text = content or ""
            finish_reason = choice.get("finish_reason")
            reasoning_chars = sum(
                len(message.get(key, ""))
                for key in ("reasoning", "reasoning_content", "analysis")
                if isinstance(message.get(key), str)
            )
            completion_details = usage.get("completion_tokens_details")
            tin = usage.get("prompt_tokens") or estimate_tokens(" ".join(m["content"] for m in messages))
            tout = usage.get("completion_tokens") or estimate_tokens(text)
            return LLMResult(text, model, tin, tout, round(time.time() - t0, 2), price(model, tin, tout),
                             str(finish_reason) if finish_reason is not None else None,
                             request_max_tokens=max_tokens,
                             response_message_keys=sorted(str(k) for k in message),
                             response_content_type=type(content).__name__ if content is not None else None,
                             response_content_chars=len(text), reasoning_chars=reasoning_chars,
                             usage_completion_details=(dict(completion_details)
                                                       if isinstance(completion_details, dict) else None))
        except urllib.error.HTTPError as e:
            error_body = e.read()[:1000]
            last = f"HTTP {e.code}: {error_body!r}"
            if b"budget has been exceeded" in error_body.lower():
                raise BudgetExceeded("лимит API 500 руб. в день исчерпан; сброс в 03:00 МСК") from e
            if e.code == 400 and body.pop("response_format", None):
                continue
            if e.code not in (408, 429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            # После таймаута сервер мог уже обработать запрос и списать токены.
            # Повторять его автоматически рискованно; live_caller попробует fallback.
            reason = getattr(e, "reason", None)
            if isinstance(e, TimeoutError) or isinstance(reason, TimeoutError):
                break
        time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM недоступна ({model}): {last}")


def _balanced(text: str, start: int) -> str | None:
    """Вырезает JSON до парной закрывающей скобки"""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            esc, in_str = (False, in_str) if esc else (ch == "\\", ch != '"')
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_json(text: str | None) -> dict | list:
    """Достаёт JSON из ответа модели"""
    if text is None:
        raise JSONExtractError("пустой ответ")
    t = _THINK.sub("", text).strip()
    if m := _FENCE.search(t):
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not starts:
        raise JSONExtractError("в ответе нет JSON-объекта")
    chunk = _balanced(t, min(starts))
    if chunk is None:
        raise JSONExtractError("JSON обрезан: не закрыта скобка (увеличьте max_tokens или сократите вход)")
    try:
        return json.loads(_TRAILING_COMMA.sub(r"\1", chunk))
    except json.JSONDecodeError as e:
        raise JSONExtractError(f"невалидный JSON: {e.msg} (строка {e.lineno}, позиция {e.colno})") from e
