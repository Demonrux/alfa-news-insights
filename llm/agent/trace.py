from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prompts.pe.domain.text import to_json


@dataclass
class Trace:
    """Журнал одного прогона агента для экрана под капотом"""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    steps: list[dict] = field(default_factory=list)
    _t0: float = field(default_factory=time.time, repr=False)

    def add(self, stage: str, kind: str, name: str, **data: Any) -> None:
        """Добавляет шаг в журнал"""
        self.steps.append({"n": len(self.steps) + 1, "stage": stage, "kind": kind, "name": name,
                           "t_ms": int((time.time() - self._t0) * 1000), **data})

    def llm(self, stage: str, prompt_version: str, res: Any, ms: int, ok: bool, **data: Any) -> None:
        """Записывает вызов модели с токенами, стоимостью и временем"""
        self.add(stage, "llm", prompt_version.split("@")[0], prompt=prompt_version, model=res.model,
                        tokens_in=res.tokens_in, tokens_out=res.tokens_out, cost_rub=res.cost_rub, ms=ms, ok=ok, **data)

    def tool(self, stage: str, name: str, args: dict, result: Any, reason: str, ms: int) -> None:
        """Записывает вызов инструмента и коротко его результат"""
        text = result if isinstance(result, str) else to_json(result)
        self.add(stage, "tool", name, args=args, reason=reason, result_chars=len(text), result_preview=text[:200], ms=ms)

    def summary(self) -> dict:
        """Считает итоги прогона"""
        calls = [s for s in self.steps if s["kind"] == "llm"]
        cost = [s["cost_rub"] for s in calls if s.get("cost_rub") is not None]
        return {"run_id": self.run_id, "steps": len(self.steps), "llm_calls": len(calls),
                "prompts": sorted({s["prompt"] for s in calls}),
                "tools": [s["name"] for s in self.steps if s["kind"] == "tool"],
                "tokens_in": sum(s["tokens_in"] for s in calls), "tokens_out": sum(s["tokens_out"] for s in calls),
                "cost_rub": round(sum(cost), 4) if cost else None,
                "fix_iterations": sum(s["name"] == "p8_fix" for s in calls),
                "duration_ms": int((time.time() - self._t0) * 1000)}

    def to_dict(self) -> dict:
        """Отдаёт журнал целиком"""
        return {"run_id": self.run_id, "started_at": self.started_at, "summary": self.summary(), "steps": self.steps}

    def save(self, directory: str | Path | None = None) -> Path | None:
        """Сохраняет журнал в файл, если задана папка"""
        directory = directory or os.environ.get("PE_TRACE_DIR")
        if not directory:
            return None
        path = Path(directory) / f"{self.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(to_json(self.to_dict(), pretty=True), encoding="utf-8")
        return path
