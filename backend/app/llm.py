"""Small OpenAI-compatible client with task routing and RUB usage accounting.

Model IDs and prices are deployment-specific. Configure the approved model alias
for each task and the provider's actual model ID in the environment; prices are
entered in RUB per one million tokens. Missing prices are reported as unknown,
never as zero.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_BASE_URL = "https://changellenge.up.railway.app/v1"


class ModelName(str, Enum):
    GEMMA_4_26B_A4B = "Gemma 4 26B A4B"
    GLM_5_3_FLASH = "GLM-5.3-Flash"
    QWEN3_6_35B_A3B = "Qwen3.6 35B A3B"
    DEEPSEEK_V4_1_FLASH = "DeepSeek-V4.1-Flash"
    QWEN3_VL_30B_A3B_INSTRUCT = "Qwen3-VL-30B-A3B-Instruct"
    KIMI_K2_6 = "Kimi-K2.6"


class Task(str, Enum):
    CLASSIFICATION = "classification"
    INTERPRETATION = "interpretation"
    CRITIC = "critic"
    CHAT = "chat"


_MODEL_ENV_KEYS = {
    ModelName.GEMMA_4_26B_A4B: "GEMMA_4_26B_A4B",
    ModelName.GLM_5_3_FLASH: "GLM_5_3_FLASH",
    ModelName.QWEN3_6_35B_A3B: "QWEN3_6_35B_A3B",
    ModelName.DEEPSEEK_V4_1_FLASH: "DEEPSEEK_V4_1_FLASH",
    ModelName.QWEN3_VL_30B_A3B_INSTRUCT: "QWEN3_VL_30B_A3B_INSTRUCT",
    ModelName.KIMI_K2_6: "KIMI_K2_6",
}

_DEFAULT_PROVIDER_MODEL_IDS = {
    ModelName.GEMMA_4_26B_A4B: "google/gemma-4-26b-a4b-it",
    ModelName.GLM_5_3_FLASH: "z-ai/glm-5.3-flash",
    ModelName.QWEN3_6_35B_A3B: "qwen/qwen3.6-35b-a3b",
    ModelName.DEEPSEEK_V4_1_FLASH: "deepseek/deepseek-v4.1-flash",
    ModelName.QWEN3_VL_30B_A3B_INSTRUCT: "qwen/qwen3-vl-30b-a3b-instruct",
    ModelName.KIMI_K2_6: "moonshotai/kimi-k2.6",
}

_DEFAULT_ROUTING = {
    Task.CLASSIFICATION: ModelName.GLM_5_3_FLASH,
    Task.INTERPRETATION: ModelName.QWEN3_6_35B_A3B,
    Task.CRITIC: ModelName.KIMI_K2_6,
    Task.CHAT: ModelName.QWEN3_6_35B_A3B,
}


class LLMError(RuntimeError):
    """Raised for configuration, transport, or response errors from the LLM API."""


@dataclass(frozen=True)
class ModelPricing:
    input_rub_per_million: float | None = None
    output_rub_per_million: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    task: Task
    model: ModelName
    provider_model: str | None
    content: str
    input_tokens: int | None
    output_tokens: int | None
    cost_rub: float | None
    latency_ms: int
    finish_reason: str | None


@dataclass
class UsageTotals:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    unreported_input_calls: int = 0
    unreported_output_calls: int = 0
    cost_rub: float = 0.0
    unpriced_calls: int = 0


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


_MODEL_BY_NAME = {_normalize(model.value): model for model in ModelName}


def _read_nonnegative_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise LLMError(f"{name} must be a number") from exc
    if value < 0:
        raise LLMError(f"{name} cannot be negative")
    return value


def _read_token_count(usage: Mapping[str, Any], *names: str) -> int | None:
    for name in names:
        value = usage.get(name)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                return None
    return None


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Some compatible endpoints return text as a list of content blocks.
        return "".join(
            str(part["text"])
            for part in content
            if isinstance(part, Mapping) and part.get("type") == "text" and "text" in part
        )
    return ""


class LLMClient:
    """Call approved models through an OpenAI-compatible ``/chat/completions`` API.

    Environment variables:
      * ``LLM_API_BASE`` (or legacy ``LLM_BASE_URL``) and ``LLM_API_KEY``.
      * ``LLM_MODEL_<TASK>``: approved alias for a task, e.g. ``GLM-5.3-Flash``.
      * ``LLM_MODEL_ID_<ALIAS>``: provider-specific model ID for an approved alias.
      * ``LLM_PRICE_<ALIAS>_INPUT_RUB_PER_1M`` and ``..._OUTPUT_RUB_PER_1M``.
      * ``LLM_TIMEOUT``: request timeout in seconds (defaults to 60).

    Usage totals are kept in memory for this client instance. Persist each
    ``LLMResponse`` separately if accounting must survive process restarts.
    """

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None,
                 timeout: float | None = None, http_client: httpx.Client | None = None):
        self.base_url = (
            base_url or os.getenv("LLM_API_BASE") or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL
        ).strip().rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "").strip()
        try:
            self.timeout = timeout if timeout is not None else float(os.getenv("LLM_TIMEOUT", "60"))
        except ValueError as exc:
            raise LLMError("LLM_TIMEOUT must be a number of seconds") from exc
        if self.timeout <= 0:
            raise LLMError("LLM_TIMEOUT must be greater than zero")

        self._http = http_client or httpx.Client(timeout=self.timeout)
        self._owns_http = http_client is None
        self._totals = UsageTotals()
        self._totals_lock = threading.Lock()

    def model_for(self, task: Task | str) -> ModelName:
        task = self._coerce_task(task)
        env_value = os.getenv(f"LLM_MODEL_{task.name}", "").strip()
        if not env_value:
            return _DEFAULT_ROUTING[task]
        model = _MODEL_BY_NAME.get(_normalize(env_value))
        if model is None:
            allowed = ", ".join(item.value for item in ModelName)
            raise LLMError(
                f"LLM_MODEL_{task.name} must be one of the approved aliases: {allowed}"
            )
        return model

    def complete(
        self,
        task: Task | str,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: ModelName | str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Send chat messages and return text, usage, estimated RUB cost and latency."""
        task = self._coerce_task(task)
        selected_model = self._coerce_model(model) if model is not None else self.model_for(task)
        if not self.base_url:
            raise LLMError("LLM_API_BASE is not configured")
        if not self.api_key:
            raise LLMError("LLM_API_KEY is not configured")
        if not messages:
            raise LLMError("messages cannot be empty")
        if timeout is not None and timeout <= 0:
            raise LLMError("timeout must be greater than zero")

        model_env_key = _MODEL_ENV_KEYS[selected_model]
        provider_model = os.getenv(f"LLM_MODEL_ID_{model_env_key}", "").strip()
        provider_model = provider_model or _DEFAULT_PROVIDER_MODEL_IDS[selected_model]
        payload: dict[str, Any] = {
            "model": provider_model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            if max_tokens <= 0:
                raise LLMError("max_tokens must be greater than zero")
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = dict(response_format)

        endpoint = f"{self.base_url}/chat/completions"
        started = time.perf_counter()
        try:
            response = self._http.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=timeout if timeout is not None else self.timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)

        if response.is_error:
            detail = response.text[:1000]
            raise LLMError(f"LLM API returned HTTP {response.status_code}: {detail}")
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("LLM API returned invalid JSON") from exc
        if not isinstance(data, Mapping):
            raise LLMError("LLM API response must be a JSON object")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise LLMError("LLM API response has no choices[0]")
        message = choices[0].get("message")
        if not isinstance(message, Mapping):
            raise LLMError("LLM API response has no choices[0].message")

        usage_data = data.get("usage")
        usage = usage_data if isinstance(usage_data, Mapping) else {}
        input_tokens = _read_token_count(usage, "prompt_tokens", "input_tokens")
        output_tokens = _read_token_count(usage, "completion_tokens", "output_tokens")
        pricing = self._pricing_for(selected_model)
        cost_rub = None
        if (input_tokens is not None and output_tokens is not None
                and pricing.input_rub_per_million is not None
                and pricing.output_rub_per_million is not None):
            cost_rub = (
                input_tokens * pricing.input_rub_per_million
                + output_tokens * pricing.output_rub_per_million
            ) / 1_000_000

        result = LLMResponse(
            task=task,
            model=selected_model,
            provider_model=str(data.get("model") or provider_model),
            content=_message_text(message.get("content")),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_rub=cost_rub,
            latency_ms=latency_ms,
            finish_reason=(str(choices[0]["finish_reason"])
                           if choices[0].get("finish_reason") is not None else None),
        )
        self._record_usage(result)
        return result

    def totals(self) -> UsageTotals:
        """Return a snapshot of this client's in-memory usage totals."""
        with self._totals_lock:
            return UsageTotals(**vars(self._totals))

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> LLMClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _coerce_task(task: Task | str) -> Task:
        if isinstance(task, Task):
            return task
        try:
            return Task(task.lower())
        except (AttributeError, ValueError) as exc:
            allowed = ", ".join(item.value for item in Task)
            raise LLMError(f"Unknown task {task!r}; expected one of: {allowed}") from exc

    @staticmethod
    def _coerce_model(model: ModelName | str) -> ModelName:
        if isinstance(model, ModelName):
            return model
        selected = _MODEL_BY_NAME.get(_normalize(str(model)))
        if selected is None:
            allowed = ", ".join(item.value for item in ModelName)
            raise LLMError(f"Model {model!r} is not approved; allowed models: {allowed}")
        return selected

    @staticmethod
    def _pricing_for(model: ModelName) -> ModelPricing:
        key = _MODEL_ENV_KEYS[model]
        return ModelPricing(
            input_rub_per_million=_read_nonnegative_float(
                f"LLM_PRICE_{key}_INPUT_RUB_PER_1M"
            ),
            output_rub_per_million=_read_nonnegative_float(
                f"LLM_PRICE_{key}_OUTPUT_RUB_PER_1M"
            ),
        )

    def _record_usage(self, result: LLMResponse) -> None:
        with self._totals_lock:
            self._totals.calls += 1
            if result.input_tokens is None:
                self._totals.unreported_input_calls += 1
            else:
                self._totals.input_tokens += result.input_tokens
            if result.output_tokens is None:
                self._totals.unreported_output_calls += 1
            else:
                self._totals.output_tokens += result.output_tokens
            if result.cost_rub is None:
                self._totals.unpriced_calls += 1
            else:
                self._totals.cost_rub += result.cost_rub
