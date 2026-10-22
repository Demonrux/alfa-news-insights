import json
from dataclasses import dataclass, asdict
from typing import Optional
from collections import defaultdict

from backend.app.database.database import Database
from backend.app.database.models import Company


@dataclass
class DemoCompany:
    id: str
    client_type: str
    okved_name: str
    revenue: float
    group_revenue: float
    region: str
    label: str


def _has_flag(company: Company, key: str, value: float = 1.0) -> bool:
    return float(company.profile_json.get(key, 0.0) or 0.0) == value


def _get_grouped_candidates(db: Database) -> list[Company]:
    """
    Группирует всех CLIENT по GROUP_ID, суммирует выручку.
    Возвращает список 'главных' компаний из групп, где суммарная выручка > 15 млрд.
    """
    all_clients = db.companies.list(client_type="CLIENT", limit=200000)

    groups = defaultdict(list)
    for c in all_clients:
        gid = c.group_id or c.id
        groups[gid].append(c)

    valid_candidates = []
    for gid, members in groups.items():
        total_revenue = sum(m.revenue for m in members)

        if total_revenue > 15e9:

            main_company = max(members, key=lambda x: x.revenue)

            main_company.profile_json["group_revenue"] = total_revenue
            valid_candidates.append(main_company)

    return valid_candidates


def _row_to_demo(company: Company, label: str = "") -> DemoCompany:

    group_rev = company.profile_json.get("group_revenue", company.revenue)

    return DemoCompany(
        id=company.id,
        client_type=company.client_type or "CLIENT",
        okved_name=(company.okved_name or "")[:60],
        revenue=company.revenue,
        group_revenue=float(group_rev),
        region=company.region or "",
        label=label,
    )


def select_demo(db: Database) -> list[DemoCompany]:
    """Выбрать 6 компаний с контрастными профилями из групп > 15 млрд."""
    result: list[DemoCompany] = []

    candidates = _get_grouped_candidates(db)

    def add(company: Optional[Company], label: str) -> None:
        if company and all(c.id != company.id for c in result):
            result.append(_row_to_demo(company, label))

    # Экспортёр с кредитами
    add(
        company=next((c for c in candidates if _has_flag(c, "FTS_FLAG") and _has_flag(c, "CL_PRODUCT_LOA_MARK")), None),
        label="Экспортёр с кредитами"
    )

    # Крупный ритейлер с кредитами
    add(
        company=next((c for c in candidates if (c.okved_name or "").startswith("Торговля") and _has_flag(c, "CL_PRODUCT_LOA_MARK")), None),
        label="Крупный ритейлер с кредитами"
    )

    # Строитель с лизингом
    add(
        company=next((c for c in candidates if (c.okved_name or "").startswith("Строительство") and _has_flag(c, "CL_PRODUCT_LEA_MARK")), None),
        label="Строитель с лизингом"
    )

    # Логист с ФТС
    add(
        company=next((c for c in candidates if "перевозк" in (c.okved_name or "").lower() and _has_flag(c, "FTS_FLAG")), None),
        label="Логист с ФТС"
    )

    # IT с депозитами, без кредитов
    add(
        company=next((c for c in candidates
              if "компьютер" in (c.okved_name or "").lower()
              and not _has_flag(c, "CL_PRODUCT_LOA_MARK")
              and _has_flag(c, "CL_PRODUCT_DEP_MARK")), None),
        label="IT с депозитами"
    )

    # Просто крупный производственник
    add(
        company=next((c for c in candidates if (c.okved_name or "").startswith("Производство")), None),
        label="Крупное производство"
    )

    return result


def dump_demo_json(companies: list[DemoCompany], path: str) -> None:
    payload = [asdict(c) for c in companies]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"demo: {len(payload)} компаний {path}")
