from __future__ import annotations

from collections import Counter, defaultdict

from .company import PRODUCT_FLAGS, flag_value, is_active_client, is_large_business, is_missing, revenue_rub
from .model import Refs


def clean_companies(rows: list[dict], r: Refs, artifact_min: int = 12) -> list[dict]:
    """Оставляет действующих клиентов без дублей и пустых строк"""
    counts = Counter(row.get("SYNTHETIC_U") for row in rows)
    seen, out = set(), []
    for row in rows:
        uid = row.get("SYNTHETIC_U")
        if is_missing(uid) or uid in seen or counts[uid] >= artifact_min or is_active_client(row, r) is False:
            continue
        seen.add(uid)
        out.append(row)
    return out


def summarize_groups(rows: list[dict], r: Refs) -> dict[str, dict]:
    """Считает размер и выручку групп компаний"""
    out: dict[str, dict] = {}
    for row in rows:
        gid = row.get("GROUP_ID")
        if is_missing(gid):
            continue
        g = out.setdefault(gid, {"size": 0, "revenue_total": 0.0, "industries": [], "products": [], "fts_countries": []})
        g["size"] += 1
        g["revenue_total"] += revenue_rub(row.get("REVENUE_COMPANY"), r) or 0.0
        for key, val in (("industries", row.get("MAINOKVED_CODE")), ("fts_countries", row.get("FTS_COUNTRY_NAME"))):
            if not is_missing(val) and val not in g[key]:
                g[key].append(val)
        g["products"] += [f for f in PRODUCT_FLAGS if flag_value(row.get(f), r) and f not in g["products"]]
    for g in out.values():
        g["large"] = is_large_business(g["revenue_total"], r)
    return out


def counterparties_from_payments(company_id: str, payments: list[dict], companies: dict[str, dict]) -> list[dict]:
    """Находит контрагентов по платежам без переводов самой себе"""
    flows: dict[tuple[str, str], dict] = {}
    for p in payments:
        payer, ben = p.get("PAYER"), p.get("BENEFICIARY")
        if payer == ben or company_id not in (payer, ben):
            continue
        other, direction = (payer, "buyer") if ben == company_id else (ben, "supplier")
        f = flows.setdefault((other, direction), {"amt": 0.0, "cnt": 0})
        f["amt"] += float(p.get("PAY_AMT") or 0)
        f["cnt"] += int(float(p.get("PAY_CNT") or 0))
    totals = defaultdict(float)
    for (_, d), f in flows.items():
        totals[d] += f["amt"]
    me = companies.get(company_id, {})
    out = []
    for (other, d), f in flows.items():
        c = companies.get(other, {})
        same_group = not is_missing(me.get("GROUP_ID")) and me.get("GROUP_ID") == c.get("GROUP_ID")
        out.append({"direction": "affiliate" if same_group else d, "share": f["amt"] / totals[d] if totals[d] else 0.0,
                    "pay_cnt": f["cnt"], "okved": c.get("MAINOKVED_CODE"), "fts_flag": c.get("FTS_FLAG"),
                    "known": bool(c)})
    return out
