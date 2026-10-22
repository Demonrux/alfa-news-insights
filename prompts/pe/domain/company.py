from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .model import Refs
from .text import plural, round_share

PRODUCT_FLAGS = ("CL_PRODUCT_LOA_MARK", "CL_PRODUCT_LEA_MARK", "CL_PRODUCT_DEP_MARK", "CL_PRODUCT_GAR_MARK",
                 "CL_PRODUCT_ZPP_MARK", "FACTORING_MARK", "CL_PRODUCT_RKO_MARK")
EFFECT_RU = {"risk": "риск", "opportunity": "возможность", "mixed": "двоякое влияние", None: "влияние"}


def is_missing(v: Any) -> bool:
    """Проверяет, что значение в данных пустое"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return True
    return str(v).strip().lower() in ("", "nan", "none", "null", "n/a", "-")


def flag_value(v: Any, r: Refs) -> bool | None:
    """Читает флаг признака как да, нет или нет данных"""
    if is_missing(v):
        return None
    s = str(v).strip()
    if s in r.features["truthy"]:
        return True
    if s in r.features["falsy"]:
        return False
    try:
        return float(s) > 0
    except ValueError:
        return None


def label(feature: str, value: Any, r: Refs) -> str:
    """Возвращает понятную подпись значения"""
    return r.features.get("value_labels", {}).get(feature, {}).get(str(value), str(value).strip())


def revenue_rub(value: Any, r: Refs) -> float | None:
    """Возвращает выручку в рублях или ничего, если это заглушка"""
    if is_missing(value):
        return None
    d = r.features["revenue"]
    try:
        rub = float(value) * float(d.get("revenue_unit_rub", 1))
    except ValueError:
        return None
    return None if rub <= float(d.get("stub_max_rub", 1000)) else rub


def revenue_band(value: Any, r: Refs) -> str:
    """Возвращает диапазон выручки вместо точной суммы"""
    rub = revenue_rub(value, r)
    if rub is None:
        return "— нет данных"
    for lo, hi, text in r.features["revenue"]["bands_bln_rub"]:
        if rub / 1e9 >= lo and (hi is None or rub / 1e9 < hi):
            return text
    return "— нет данных"


def is_large_business(rub: float | None, r: Refs) -> bool:
    """Проверяет, что выручка группы выше порога крупного бизнеса"""
    return rub is not None and rub > float(r.features["revenue"].get("large_business_bln_rub", 15)) * 1e9


def okved2(code: Any) -> str | None:
    """Берёт первые две цифры ОКВЭД"""
    if is_missing(code):
        return None
    head = "".join(ch for ch in str(code) if ch.isdigit() or ch == ".").split(".")[0]
    return head.zfill(2)[:2] if head else None


def industry_name(code2: str | None, r: Refs) -> str:
    """Возвращает название отрасли по ОКВЭД"""
    if not code2:
        return "отрасль не указана"
    return r.features["okved_sections"].get(code2, f"ОКВЭД {code2}")


def is_active_client(row: dict, r: Refs) -> bool | None:
    """Проверяет, что компания действующий клиент"""
    v = row.get("CL_TYPE")
    return None if is_missing(v) else str(v).strip() in r.features.get("active_client_values", ["Client"])


def group_line(group: dict | None, r: Refs) -> str | None:
    """Пишет строку о группе компаний"""
    if not group:
        return None
    d = r.features
    rub = revenue_rub(group.get("revenue_total"), r)
    large = is_large_business(rub, r)
    inds = list(dict.fromkeys(industry_name(okved2(c), r) for c in group.get("industries") or []))
    products = [d["flags"][f]["label"] for f in group.get("products") or [] if f in d["flags"]]
    parts = []
    if group.get("size"):
        parts.append(plural(int(group["size"]), "компания", "компании", "компаний"))
    if rub is not None:
        parts.append(f"совокупная выручка за {d['revenue'].get('year', '')} г. {revenue_band(rub, r)}"
                     + (" — крупный бизнес" if large else ""))
    if inds:
        parts.append("отрасли: " + ", ".join(inds[:5]))
    if products:
        parts.append("продукты банка в группе: " + ", ".join(products))
    if group.get("fts_countries"):
        parts.append("ВЭД группы: " + ", ".join(group["fts_countries"][:5]))
    return "Группа компаний: " + "; ".join(parts) if parts else "Входит в группу компаний"


def portrait(row: dict, r: Refs, group: dict | None = None) -> dict:
    """Собирает портрет компании без идентификаторов и точных сумм"""
    flags = r.features["flags"]
    yes, no, unknown = [], [], []
    for f in PRODUCT_FLAGS:
        if f in row:
            v = flag_value(row.get(f), r)
            (yes if v else no if v is False else unknown).append(flags[f]["if_true"] if v else flags[f]["label"])
    fts, fts_line = flag_value(row.get("FTS_FLAG"), r), None
    if fts:
        country = row.get("FTS_COUNTRY_NAME")
        fts_line = "ВЭД: есть сведения в базе ФТС" + ("" if is_missing(country) else f", страна — {str(country).strip()}")
    elif fts is False:
        fts_line = "ВЭД: сведений в базе ФТС нет"
    elif "FTS_FLAG" in row:
        unknown.append("ВЭД")
    org = [f"{name} — {label(f, row[f], r)}" for f, name in (("ORG_TYPE", "тип организации"), ("OKFS_NAME", "форма собственности"))
           if not is_missing(row.get(f))]
    workers = row.get("AMOUNT_WORKERS_FNS_GRADATION")
    workers = row.get("AMOUNT_WORKERS_SPARK_GRADATION") if is_missing(workers) else workers
    has_rev = revenue_rub(row.get("REVENUE_COMPANY"), r) is not None

    def val(f: str) -> str | None:
        """Возвращает подпись значения или ничего"""
        return None if is_missing(row.get(f)) else label(f, row[f], r)

    p = {
        "okved_code": val("MAINOKVED_CODE"), "okved_name": val("MAINOKVED_NAME"),
        "industry": industry_name(okved2(row.get("MAINOKVED_CODE")), r),
        "org_line": ("; ".join(org)[:1].upper() + "; ".join(org)[1:]) if org else None,
        "revenue_band": revenue_band(row.get("REVENUE_COMPANY"), r)
                        + (f" (за {r.features['revenue'].get('year')} г.)" if has_rev else ""),
        "workers": None if is_missing(workers) else label("AMOUNT_WORKERS_FNS_GRADATION", workers, r),
        "age": val("COMPANY_AGE_YEARS_GRADATION"), "eco_stage": val("ECO_MARK_LABEL"),
        "region": val("REGION"), "city": val("CITY"),
        "products_yes": yes, "products_no": no, "fts_line": fts_line,
        "group_line": group_line(group, r) or (None if is_missing(row.get("GROUP_ID")) else "Входит в группу компаний"),
        "client_type": val("CL_TYPE"), "unknown": unknown,
    }
    if p["okved_code"] is None:
        unknown.append("отрасль")
    return p


def feature_refs(row: dict, r: Refs) -> dict[str, str]:
    """Создаёт ссылки на известные признаки компании"""
    out = {}
    for f, spec in r.features["flags"].items():
        v = flag_value(row.get(f), r) if f in row else None
        if v is not None:
            out[f"feature:{f}"] = spec["if_true"] if v else spec["if_false"]
    for f, name in r.features["categorical"].items():
        if f in row and not is_missing(row.get(f)):
            out[f"feature:{f}"] = f"{name}: {label(f, row[f], r)}"
    if not is_missing(row.get("MAINOKVED_CODE")):
        out["feature:MAINOKVED_CODE"] = f"основной ОКВЭД {row['MAINOKVED_CODE']}"
    if revenue_rub(row.get("REVENUE_COMPANY"), r) is not None:
        out["feature:REVENUE_COMPANY"] = f"выручка {revenue_band(row['REVENUE_COMPANY'], r)}"
    if not is_missing(row.get("GROUP_ID")):
        out["feature:GROUP_ID"] = "входит в группу компаний"
    return out


def counterparties(rows: list[dict], r: Refs, top: int = 4) -> dict:
    """Группирует контрагентов по отраслям с округлёнными долями"""
    by_dir: dict[str, list[dict]] = defaultdict(list)
    for row in rows or []:
        if not (row.get("self") or row.get("direction") == "self"):
            by_dir[row.get("direction", "")].append(row)

    def groups(items: list[dict], kind: str) -> tuple[list[dict], str, int]:
        """Группирует контрагентов одного направления по отраслям"""
        agg: dict[str, dict] = {}
        for row in items:
            g = agg.setdefault(okved2(row.get("okved")) or "", {"share": 0.0, "fts": False, "regular": False})
            g["share"] += float(row.get("share") or 0)
            g["fts"] |= bool(flag_value(row.get("fts_flag"), r))
            g["regular"] |= int(row.get("pay_cnt") or 0) >= 12
        out = []
        for code, g in sorted(agg.items(), key=lambda kv: -kv[1]["share"])[:top]:
            ind = industry_name(code or None, r) if code else "нет информации об отрасли"
            line = ind + (f" (ОКВЭД {code})" if code else "") + f": около {round_share(g['share'])}"
            line += ", среди них есть участники ВЭД" if g["fts"] else ""
            line += ", регулярные платежи" if g["regular"] else ""
            out.append({"okved": code or None, "industry": ind, "share": round_share(g["share"]), "line": line,
                        "ref": f"cp:{kind}_{code or 'na'}"})
        return out, round_share(sum(g["share"] for g in agg.values())), len(items)

    buyers, b_share, b_n = groups(by_dir.get("buyer", []), "buyers")
    suppliers, s_share, s_n = groups(by_dir.get("supplier", []), "suppliers")
    aff = by_dir.get("affiliate", [])
    affiliates = [plural(len(aff), "компания", "компании", "компаний") + ": "
                  + ", ".join(sorted({industry_name(okved2(x.get("okved")), r) for x in aff})[:5])] if aff else []
    return {"buyers": buyers, "buyers_share": b_share, "buyers_count": b_n,
            "buyers_count_text": plural(b_n, "ключевой", "ключевых", "ключевых"),
            "suppliers": suppliers, "suppliers_share": s_share, "suppliers_count": s_n,
            "suppliers_count_text": plural(s_n, "ключевой", "ключевых", "ключевых"), "affiliates": affiliates}


def cp_refs(rows: list[dict], r: Refs, group: dict | None = None) -> dict[str, str]:
    """Создаёт ссылки на группу и контрагентов"""
    c = counterparties(rows, r)
    out = {}
    if group and group.get("size"):
        out["cp:group"] = group_line(group, r)[:160]
    if c["buyers"]:
        out["cp:buyers"] = f"ключевые покупатели: {c['buyers_count']}, около {c['buyers_share']} поступлений"
    out.update({g["ref"]: f"покупатели — {g['industry']}: около {g['share']}" for g in c["buyers"]})
    if c["suppliers"]:
        out["cp:suppliers"] = f"ключевые поставщики: {c['suppliers_count']}, около {c['suppliers_share']} платежей"
    out.update({g["ref"]: f"поставщики — {g['industry']}: около {g['share']}" for g in c["suppliers"]})
    if c["affiliates"]:
        out["cp:affiliates"] = "связанные компании: " + c["affiliates"][0]
    return out


def sensitivity(row: dict, r: Refs, event: dict | None = None) -> dict[str, dict]:
    """Показывает, к каким факторам чувствительна компания"""
    out: dict[str, dict] = {}

    def add(factor: str, weight: float, effect: str | None, why: str, feature: str) -> None:
        """Добавляет вклад признака в фактор"""
        cur = out.setdefault(factor, {"weight": 0.0, "effect": effect, "why": [], "features": [], "items": []})
        cur["weight"] = round(min(1.0, cur["weight"] + weight), 2)
        cur["effect"] = cur["effect"] if cur["effect"] == effect else "mixed"
        cur["why"].append(why)
        cur["features"].append(feature)
        cur["items"].append({"feature": feature, "effect": effect, "weight": weight, "why": why})

    ev_countries = {c.lower() for c in (event or {}).get("geography", {}).get("countries", [])}
    ev_regions = {c.lower() for c in (event or {}).get("geography", {}).get("regions", [])}
    for rule in r.matrix["rules"]:
        f, v = rule["feature"], row.get(rule["feature"])
        if rule.get("multiplier") or rule.get("aggregate"):
            continue
        if rule.get("match_event"):
            pool = ev_countries if rule["match_event"] == "countries" else ev_regions
            ok = not is_missing(v) and str(v).strip().lower() in pool
        elif "value" in rule:
            ok = flag_value(v, r) is True if rule["value"] == 1 else str(v) == str(rule["value"])
        elif "value_contains" in rule:
            ok = not is_missing(v) and rule["value_contains"].lower() in str(v).lower()
        else:
            ok = False
        if ok:
            add(rule["factor"], rule["weight"], rule["effect"], rule["explanation"], f)
    code = okved2(row.get("MAINOKVED_CODE"))
    for factor in r.matrix.get("okved_factors", {}).get(code, []):
        add(factor, 0.3, None, f"отрасль «{industry_name(code, r)}» чувствительна к фактору", "MAINOKVED_CODE")
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["weight"]))


def _component_ref(c: dict) -> str:
    """Подбирает ссылку для причины отбора"""
    if c.get("kind") == "graph":
        d = c.get("direction", "buyers")
        return f"cp:{d if d.endswith('s') else d + 's'}_{okved2(c.get('okved')) or 'na'}"
    return f"feature:{c.get('feature') or 'MAINOKVED_CODE'}"


def _why(c: dict, r: Refs) -> str:
    """Объясняет одну причину отбора понятными словами"""
    expl = c.get("explanation") or ""
    if c.get("kind") != "graph" or c.get("share") is None:
        return expl
    ind, share = industry_name(okved2(c.get("okved")), r), round_share(float(c["share"]))
    head = (f"около {share} поступлений — от покупателей из отрасли «{ind}»" if str(c.get("direction", "buyer")).startswith("buyer")
            else f"около {share} платежей — поставщикам из отрасли «{ind}»")
    return head + (f"; {expl}" if expl else "")


def relevance_items(components: list[dict], r: Refs) -> list[dict]:
    """Превращает причины отбора в понятные пункты по убыванию вклада"""
    top = sorted(components or [], key=lambda x: -float(x.get("contribution") or 0))
    return [{"ref": _component_ref(c), "factor": c["factor"], "factor_name": r.factor_names.get(c["factor"], c["factor"]),
             "effect": c.get("effect"), "contribution": float(c.get("contribution") or 0), "explanation": _why(c, r)} for c in top]


def relevance_block(components: list[dict], r: Refs) -> str:
    """Готовит причины отбора для промпта"""
    lines = [f"- [{it['ref']}] {it['factor']} ({EFFECT_RU.get(it['effect'], 'влияние')}), вклад {it['contribution']:.2f}: "
             f"{it['explanation']}" for it in relevance_items(components, r)[:6]]
    return "\n".join(lines) or "- Вклад факторов не передан."
