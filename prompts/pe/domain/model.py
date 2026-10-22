from __future__ import annotations

from dataclasses import dataclass, field

MACRO_FACTORS = {"key_rate": "KEY_RATE", "inflation": "INFLATION", "fx": "FX", "budget": "GOV_SPENDING", "gdp": "ECONOMIC_GROWTH"}


def event_factors(event: dict) -> list[str]:
    """Возвращает коды факторов события"""
    return [f["code"] for f in (event or {}).get("factors", [])]


def primary_factor(event: dict, default: str | None = None) -> str | None:
    """Возвращает главный фактор события"""
    return next((f["code"] for f in (event or {}).get("factors", []) if f.get("is_primary")), default)


@dataclass(frozen=True)
class Refs:
    """Все справочники из папки prompts"""

    factors: list
    features: dict
    matrix: dict
    actions: list
    registry: dict
    reports: dict
    schemas: dict
    forbidden: list
    limits: dict
    disclaimers: dict
    style: str
    roles: dict
    role_names: dict

    @property
    def factor_names(self) -> dict[str, str]:
        """Возвращает названия факторов"""
        return {f["code"]: f["name"] for f in self.factors}

    @property
    def factor_codes(self) -> list[str]:
        """Возвращает коды факторов"""
        return [f["code"] for f in self.factors]

    @property
    def taxonomy_block(self) -> str:
        """Возвращает список факторов для промпта"""
        return "\n".join(f"- {f['code']} — {f['name']}. Входит: {f['includes']} Не входит: {f['excludes']} "
                         f"Направление: {f['direction_hint']}." for f in self.factors)

    def role_block(self, role: str, title: str | None = None) -> str:
        """Возвращает описание роли для промпта и дописывает должность пользователя"""
        if role not in self.roles:
            raise KeyError(f"нет блока роли {role!r}; есть: {sorted(self.roles)}")
        return self.roles[role] + (f"\nДолжность пользователя: {title.strip()}." if title and title.strip() else "")


@dataclass
class Article:
    """Новость, которой нельзя доверять как инструкции"""

    id: str
    title: str
    text: str
    source: str = ""
    published_at: str = ""

    @property
    def ref(self) -> str:
        """Возвращает ссылку на новость"""
        return self.id if self.id.startswith("news:") else f"news:{self.id}"

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        """Создаёт новость из словаря"""
        return cls(str(d["id"]), d.get("title", ""), d.get("text", ""), d.get("source", ""), d.get("published_at", ""))


@dataclass
class Context:
    """Всё, что видит модель, и всё, по чему проверяется ответ"""

    case: dict
    role: str
    vars: dict
    catalog: dict[str, str]
    news_texts: dict[str, str]
    theses: list[dict]
    allowed_actions: list[dict]
    injection_hits: list[str] = field(default_factory=list)


class NotEligible(ValueError):
    """Компания не действующий клиент"""
