import json
from dataclasses import dataclass, asdict
from typing import Optional

from app.database.database import Database
from app.database.models import Company


@dataclass
class DemoCompany:
    id: str
    client_type: str
    okved_name: str
    revenue: float
    region: str
    label: str


def _has_flag(company: Company, key: str, value: float = 1.0) -> bool:
    return float(company.profile_json.get(key, 0.0) or 0.0) == value


def _row_to_demo(company: Company, label: str = "") -> DemoCompany:
    return DemoCompany(
        id=company.id,
        client_type=company.client_type,
        okved_name=company.okved_name,
        revenue=company.revenue,
        region=company.region,
        label=label,
    )


def select_demo(db: Database) -> list[DemoCompany]:
    """Выбрать 6 компаний с контрастными профилями."""
    result: list[DemoCompany] = []

    def add(company: Optional[Company], label: str = "") -> None:
        if company and all(c.id != company.id for c in result):
            result.append(_row_to_demo(company, label))

    # Крупный экспортёр с кредитами
    candidates = db.companies.list(
        client_type="CLOSE_CLIENT", min_revenue=5e9, limit=300,
    )

    add(next((c for c in candidates
             if _has_flag(c, "FTS_FLAG") and _has_flag(c, "CL_PRODUCT_LOA_MARK")), None))

    # Крупный ритейлер с кредитами
    candidates = db.companies.list(
        client_type="CLOSE_CLIENT", min_revenue=2e9,
        okved_name_prefix="Торговля", limit=300,
    )

    add(next((c for c in candidates if _has_flag(c, "CL_PRODUCT_LOA_MARK")), None))

    # Строитель с лизингом
    candidates = db.companies.list(
        min_revenue=1e9, okved_name_prefix="Строительство", limit=300,
    )
    add(next((c for c in candidates if _has_flag(c, "CL_PRODUCT_LEA_MARK")), None))

    # Логист с ФТС
    candidates = db.companies.list(
        min_revenue=500e6, okved_name_prefix="Деятельность вспомогательная", limit=300,
    )
    candidates = [c for c in candidates if "перевозк" in c.okved_name.lower()]
    add(next((c for c in candidates if _has_flag(c, "FTS_FLAG")), None))

    # IT с депозитами, без кредитов
    candidates = db.companies.list(
        min_revenue=500e6, okved_name_prefix="Торговля оптовая компьютерами", limit=300,
    )
    add(next((c for c in candidates
             if not _has_flag(c, "CL_PRODUCT_LOA_MARK")
             and _has_flag(c, "CL_PRODUCT_DEP_MARK")), None))

    # Потенциальный клиент
    candidates = db.companies.list(
        client_type="PROSPECT", min_revenue=2e9, limit=1,
    )
    add(candidates[0] if candidates else None)

    return result


def dump_demo_json(companies: list[DemoCompany], path: str) -> None:
    payload = [asdict(c) for c in companies]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"demo: {len(payload)} компаний {path}")
