from __future__ import annotations

from ..domain import company as co
from ..domain.model import Article, Context, NotEligible, Refs, event_factors, primary_factor
from ..domain.text import detect_injection, neutralize, to_json, wrap_article, wrap_untrusted
from ..infra.repo import refs, render_template


def _ref(prefix: str, x: str) -> str:
    """Добавляет к идентификатору служебный префикс"""
    return x if str(x).startswith(prefix + ":") else f"{prefix}:{x}"


def _ext_text(e: dict) -> str:
    """Склеивает заголовок и текст внешнего источника"""
    return e.get("title", "") + "\n" + e.get("text", "")


def render_portrait(company: dict, group: dict | None, r: Refs) -> str:
    """Пишет портрет компании для промпта"""
    return render_template("profile.j2", p=co.portrait(company, r, group))


def render_counterparties(counterparties: list[dict], r: Refs) -> str:
    """Пишет контрагентов компании для промпта"""
    return render_template("counterparties.j2", c=co.counterparties(counterparties, r))


def review_vars(base: dict, draft: dict | None, issues: list[dict], materials: str = "") -> dict:
    """Добавляет к переменным промпта черновик и замечания для критика и исправления"""
    return {**base, "draft_json": to_json(draft or {}), "insight_json": to_json(draft or {}), "precheck_block": to_json(issues),
            "issues_json": to_json(issues), "new_materials_block": materials}


def select_theses(event: dict, company: dict | None, r: Refs, max_n: int = 6) -> list[dict]:
    """Подбирает актуальные тезисы ЦМИ под событие и отрасль компании"""
    factors = event_factors(event)
    primary = primary_factor(event, factors[0] if factors else None)
    okveds = set(event.get("okved_hints", [])) | ({co.okved2(company.get("MAINOKVED_CODE"))} - {None} if company else set())
    scored = []
    for t in r.registry.values():
        if t["status"] != "current":
            continue
        s = (3 if t["factors"][0] == primary else 2) if primary in t["factors"] else 0
        s += sum(f != primary and f in t["factors"] for f in factors) + (1.5 if set(t["okved_hints"]) & okveds else 0)
        if s > 0:
            scored.append((s + 0.001 * int(t["report_date"].replace("-", "")), t))
    return [t for _, t in sorted(scored, key=lambda x: -x[0])[:max_n]]


def theses_block(theses: list[dict]) -> str:
    """Готовит тезисы ЦМИ для промпта"""
    return "\n".join(f"- {t['thesis_id']} | «{t['report_title']}» от {t['report_date']} | {', '.join(t['factors'])} | "
                     f"{t['thesis']}" + (f" Прогноз: {t['forecast']}." if t.get("forecast") else "")
                     for t in theses) or "Подходящих тезисов ЦМИ нет."


def allowed_actions(event_factors: list[str], company: dict, role: str, r: Refs, components: list[dict] | None = None) -> list[dict]:
    """Выбирает продукты банка, которые можно предложить в этой карточке"""
    comp = {(c.get("factor"), c.get("feature")): c.get("effect") for c in components or []}
    matrix = {(m["feature"], m.get("factor")): m.get("effect") for m in r.matrix["rules"]}
    out = []
    for rule in r.actions:
        w = rule["when"]
        if w["factor"] not in event_factors or co.flag_value(company.get(w["feature"]), r) is not True:
            continue
        if "effect" in w and (comp.get((w["factor"], w["feature"])) or matrix.get((w["feature"], w["factor"]))) != w["effect"]:
            continue
        if not rule.get("roles") or role in rule["roles"]:
            out.append(rule)
    return out


def actions_block(rules: list[dict]) -> str:
    """Готовит список разрешённых действий для промпта"""
    return "\n".join(f"- rule_id={x['id']} | продукт: {x['product'] or 'нет'} | cta: {x.get('cta') or 'null'} | {x['action']}"
                     for x in rules) or "Нет. Продукты банка в этой карточке не предлагай; все действия — analysis или operational, cta = null."


def catalog_block(catalog: dict[str, str]) -> str:
    """Готовит список ссылок, на которые модели можно опираться"""
    titles = {"news": "Статьи", "T-": "Тезисы ЦМИ", "chunk": "Фрагменты отчётов", "ext": "Внешние данные (не позиция банка)",
              "feature": "Признаки компании", "cp": "Контрагенты и группа"}
    groups: dict[str, list[str]] = {}
    for ref, desc in catalog.items():
        groups.setdefault("T-" if ref.startswith("T-") else ref.split(":", 1)[0], []).append(f"- {ref} — {desc}")
    return "\n".join(f"{t}:\n" + "\n".join(groups[k]) for k, t in titles.items() if groups.get(k))


def _case_theses(case: dict, r: Refs) -> list[dict]:
    """Берёт тезисы из кейса или подбирает их сам"""
    if case.get("theses"):
        return [r.registry[t] for t in case["theses"] if r.registry.get(t, {}).get("status") == "current"]
    return select_theses(case.get("event", {}), case.get("company") or {}, r)


def _catalog(arts: list[Article], theses: list[dict], chunks: list[dict], external: list[dict], r: Refs) -> dict[str, str]:
    """Собирает ссылки на статьи, тезисы, фрагменты отчётов и внешние источники"""
    out = {a.ref: f"{a.source + ': ' if a.source else ''}{neutralize(a.title)[:120]}" for a in arts}
    out |= {t["thesis_id"]: f"ЦМИ, «{t['report_title']}» от {t['report_date']}" for t in theses}
    out |= {_ref("chunk", c["id"]): f"фрагмент отчёта {c.get('report_id', '')}".strip() for c in chunks}
    return out | {_ref("ext", e["id"]): f"{e.get('source', 'внешний источник')}: {neutralize(e.get('title', ''))[:100]}" for e in external}


def build_context(case: dict, role: str | None = None, r: Refs | None = None) -> Context:
    """Собирает всё, что модель увидит о новости, компании и пользователе"""
    r = r or refs()
    role = role or case.get("role", "cfo")
    event, company = case.get("event", {}), case.get("company") or {}
    cps, comps = case.get("counterparties") or [], case.get("components") or []
    arts = [Article.from_dict(a) for a in case.get("articles", [])]
    chunks, external = case.get("chunks") or [], case.get("external") or []
    if co.is_active_client(company, r) is False:
        raise NotEligible(f"CL_TYPE={company.get('CL_TYPE')}: сервис только для действующих клиентов")
    group = case.get("group") or ({"size": case["group_size"]} if case.get("group_size") else None)
    theses = _case_theses(case, r)
    rules = allowed_actions(event_factors(event), company, role, r, comps)
    catalog = _catalog(arts, theses, chunks, external, r) | co.feature_refs(company, r) | co.cp_refs(cps, r, group)
    texts = {a.ref: a.title + "\n" + a.text for a in arts}
    texts |= {_ref("ext", e["id"]): _ext_text(e) for e in external}
    v = {
        "today": case.get("today", ""), "role": role, "role_block": r.role_block(role, case.get("user_title")), "style_block": r.style,
        "taxonomy_block": r.taxonomy_block, "event_json": to_json(event),
        "articles_block": "\n\n".join(wrap_article(a) for a in arts),
        "portrait": render_portrait(company, group, r), "counterparties": render_counterparties(cps, r),
        "relevance_block": co.relevance_block(comps, r), "theses_block": theses_block(theses),
        "chunks_block": "\n".join(wrap_untrusted("report", _ref("chunk", c["id"]), c["text"]) for c in chunks),
        "external_block": "\n".join(wrap_untrusted("external", _ref("ext", e["id"]), _ext_text(e),
                                                   source=e.get("source", ""), url=e.get("url", "")) for e in external),
        "actions_block": actions_block(rules), "ref_catalog": catalog_block(catalog),
    }
    hits = [h for t in texts.values() for h in detect_injection(t)]
    return Context(case, role, v, catalog, texts, theses, rules, hits)
