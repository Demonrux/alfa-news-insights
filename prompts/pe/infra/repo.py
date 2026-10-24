from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..domain.model import Refs

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = Path(os.environ.get("PE_PROMPTS_DIR", ROOT / "prompts"))
CASES = PROMPTS / "cases"
REPORTS_TEXT = Path(os.environ.get("PE_REPORTS_DIR", PROMPTS / "reports_text"))
RUNS = Path(os.environ.get("PE_RUNS_DIR", ROOT / "runs"))
MODELS_FILE = Path(os.environ.get("PE_MODELS_FILE", ROOT / "llm" / "models.yaml"))
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _env(**kw: Any) -> Environment:
    """Создаёт шаблонизатор, который ругается на пропущенные переменные"""
    return Environment(loader=FileSystemLoader([str(PROMPTS), str(PROMPTS / "templates")]), undefined=StrictUndefined,
                       autoescape=False, **kw)


@dataclass
class Prompt:
    """Промпт с настройками и текстами"""

    id: str
    meta: dict
    system: str
    user: str

    @property
    def version(self) -> str:
        """Возвращает версию промпта"""
        return f"{self.id}@v{self.meta.get('version', 0)}"

    @property
    def schema_name(self) -> str:
        """Возвращает имя схемы ответа без расширения"""
        return str(self.meta.get("schema", "")).removesuffix(".json")

    @property
    def inputs(self) -> list[str]:
        """Возвращает обязательные переменные промпта"""
        return list(self.meta.get("inputs", []))

    def render(self, **variables: Any) -> list[dict]:
        """Собирает сообщения для модели"""
        if missing := [n for n in self.inputs if n not in variables]:
            raise KeyError(f"{self.id}: не переданы переменные {missing}")
        env = _env(keep_trailing_newline=True)
        return [{"role": role, "content": env.from_string(t).render(**variables).strip()}
                for role, t in (("system", self.system), ("user", self.user))]


def load_prompt(name: str | Path) -> Prompt:
    """Загружает промпт по имени"""
    path = Path(name)
    if not path.exists():
        cand = list(PROMPTS.glob(f"{name}*.md"))
        if len(cand) != 1:
            raise FileNotFoundError(f"промпт {name!r} не найден в {PROMPTS}")
        path = cand[0]
    text = path.read_text(encoding="utf-8")
    m = _FRONT.match(text)
    body = text[m.end():] if m else ""
    if not m or "<<<SYSTEM>>>" not in body or "<<<USER>>>" not in body:
        raise ValueError(f"{path}: нужны блок метаданных --- и маркеры <<<SYSTEM>>>, <<<USER>>>")
    meta = yaml.safe_load(m.group(1)) or {}
    system, user = body.split("<<<SYSTEM>>>", 1)[1].split("<<<USER>>>", 1)
    return Prompt(meta["id"], meta, system, user)


def render_template(name: str, **kw: Any) -> str:
    """Заполняет шаблон данными"""
    return _env(trim_blocks=True, lstrip_blocks=True).get_template(name).render(**kw).strip()


def load_yaml(path: str | Path) -> Any:
    """Читает YAML файл"""
    p = Path(path)
    return yaml.safe_load((p if p.is_absolute() or p.exists() else PROMPTS / p).read_text(encoding="utf-8"))


def load_cases(path: str | Path) -> list[dict]:
    """Читает тестовые кейсы"""
    data = load_yaml(path)
    return data["cases"] if isinstance(data, dict) else data


def _split(v: str) -> list[str]:
    """Делит строку по точке с запятой"""
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def _style() -> tuple[str, list[str], dict[str, int]]:
    """Читает правила стиля и запрещённые фразы"""
    text = (PROMPTS / "style_guide.md").read_text(encoding="utf-8")
    block = text.split("<!-- BLOCK START -->", 1)[1].split("<!-- BLOCK END -->", 1)[0].strip()
    forbidden, limits, mode = [], {}, None
    for line in map(str.strip, text.splitlines()):
        if line in ("FORBIDDEN:", "LIMITS:"):
            mode = line[0]
        elif line.startswith("- ") and mode == "F":
            forbidden.append(line[2:].strip().lower())
        elif line.startswith("- ") and mode == "L":
            k, v = line[2:].split(":", 1)
            limits[k.strip()] = int(v)
        elif line.startswith("#"):
            mode = None
    return block, forbidden, limits


def _roles() -> tuple[dict, dict]:
    """Читает описания ролей и их названия"""
    text = (PROMPTS / "p6_roles.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(_FRONT.match(text).group(1))
    parts = re.split(r"^## (\S+)\s*$", _FRONT.sub("", text, count=1), flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}, meta["names"]


@lru_cache(maxsize=None)
def refs() -> Refs:
    """Загружает все справочники один раз"""
    with open(PROMPTS / "reports.csv", encoding="utf-8") as f:
        reports = {r["report_id"]: r for r in csv.DictReader(f)}
    registry = {}
    with open(PROMPTS / "thesis_registry.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rep = reports[row["report_id"]]
            registry[row["thesis_id"]] = {**row, "factors": _split(row["factors"]),
                                          "okved_hints": [x.zfill(2) for x in _split(row["okved_hints"])],
                                          "report_title": rep["title_in_case"], "report_date": rep["report_date"],
                                          "status": "stale" if rep["status"] == "stale" else row["status"]}
    schemas = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (PROMPTS / "schemas").glob("*.json")}
    style, forbidden, limits = _style()
    roles, names = _roles()
    return Refs(factors=load_yaml("taxonomy.yaml")["factors"], features=load_yaml("feature_dictionary.yaml"),
                matrix=load_yaml("feature_factor_matrix.yaml"), actions=load_yaml("next_actions.yaml")["rules"],
                registry=registry, reports=reports, schemas=schemas, forbidden=forbidden, limits=limits,
                disclaimers=load_yaml("disclaimers.yaml"), style=style, roles=roles, role_names=names)


def report_text(report_id: str) -> str:
    """Читает текст отчёта ЦМИ"""
    p = REPORTS_TEXT / f"{report_id}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""
