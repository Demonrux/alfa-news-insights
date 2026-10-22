from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator

from .model import Context, Refs, primary_factor
from .text import PII, jaccard, numbers, overlap, periods, sentences, to_json

SEVERITY = {
    "schema": "blocker", "invalid_source": "blocker", "fabricated_bank_view": "blocker", "stale_bank_view": "blocker",
    "wrong_fact": "blocker", "wrong_product": "blocker", "sensitive_data": "blocker", "injection_followed": "blocker",
    "no_source": "blocker", "misleading": "blocker",
    "retelling": "major", "no_personalization": "major", "single_factor": "major", "wrong_role": "major",
    "generic": "major", "contradiction": "major", "hypothesis_as_fact": "major", "no_impact_estimate": "major",
    "basis_mismatch": "major", "too_many_products": "major",
    "forbidden_phrase": "minor", "too_long": "minor",
}
_BANK_VOICE = re.compile(r"\b(альфа-)?банк\s+(считает|рекомендует|ожидает|полагает|советует)|по\s+мнению\s+(альфа-)?банка", re.I)
AI_FIELDS = ("ai_conclusions", "risks", "opportunities")
_TEXT_FIELDS = ("what_happened", "bank_view", "ai_conclusions", "hypotheses", "risks", "opportunities", "scenarios",
                "actions", "open_questions", "why_relevant")


def issue(type_: str, field: str, fix: str, item_index: int | None = None, severity: str | None = None) -> dict:
    """Создаёт запись о найденной проблеме"""
    return {"field": field, "item_index": item_index, "type": type_, "severity": severity or SEVERITY.get(type_, "major"),
            "fix": fix}


def tag(i: dict, field: bool = True) -> str:
    """Коротко описывает проблему для журнала"""
    return f"{i['severity']}:{i['type']}" + (f":{i['field']}" if field else "")


def with_severity(issues: list[dict], *levels: str) -> list[dict]:
    """Оставляет проблемы нужной тяжести"""
    return [i for i in issues if i["severity"] in levels]


def validate_schema(obj: Any, schema: dict) -> list[dict]:
    """Проверяет ответ по JSON схеме"""
    out = []
    for e in sorted(Draft202012Validator(schema).iter_errors(obj), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in e.path) or "(root)"
        out.append(issue("schema", path, f"{path}: {e.message[:200]}"))
    return out


def check_event(ev: dict, r: Refs) -> list[dict]:
    """Проверяет событие из P1"""
    out = validate_schema(ev, r.schemas["event"])
    if out:
        return out
    if ev["is_business_relevant"]:
        if sum(f["is_primary"] for f in ev["factors"]) != 1:
            out.append(issue("schema", "factors", "Должен быть ровно один фактор с is_primary = true"))
        if len({f["code"] for f in ev["factors"]}) != len(ev["factors"]):
            out.append(issue("schema", "factors", "Факторы не должны повторяться"))
    else:
        if ev["factors"]:
            out.append(issue("schema", "factors", "Для нерелевантного события factors должен быть пустым"))
        if not ev.get("irrelevance_reason"):
            out.append(issue("schema", "irrelevance_reason", "Укажите причину нерелевантности"))
    return out


def iter_texts(ins: dict):
    """Перебирает все тексты карточки"""
    if ins.get("headline"):
        yield "headline", None, ins["headline"]
    for f in _TEXT_FIELDS:
        for i, it in enumerate(ins.get(f) or []):
            if isinstance(it, str):
                yield f, i, it
            elif isinstance(it, dict):
                yield f, i, " ".join(str(it[k]) for k in ("text", "trigger", "logic", "explanation", "how_to_check") if it.get(k))
    imp = ins.get("impact") or {}
    est = imp.get("estimate") or {}
    txt = " ".join(str(x) for x in (imp.get("criterion"), est.get("range"), est.get("method"), imp.get("no_estimate_reason")) if x)
    if txt:
        yield "impact", None, txt


def _bad_refs(refs: list[str], catalog: dict) -> list[str]:
    """Находит ссылки, которых нет в контексте"""
    return [x for x in refs or [] if x not in catalog]


def _check_facts(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет, что факты и цифры взяты из статей"""
    out = []
    for i, it in enumerate(ins.get("what_happened") or []):
        refs = it.get("source_ids") or []
        if bad := _bad_refs(refs, ctx.catalog):
            out.append(issue("invalid_source", "what_happened", f"Несуществующие ссылки {bad}; используйте news:… из каталога", i))
            continue
        extra = numbers(it.get("text", "")) - numbers(" ".join(ctx.news_texts.get(x, "") for x in refs))
        if extra:
            out.append(issue("wrong_fact", "what_happened", f"Цифр {sorted(extra)} нет в статьях {refs}; уберите их или сошлитесь на нужную статью", i))
    return out


def _check_bank_view(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет, что позиция банка точно совпадает с тезисом ЦМИ"""
    out, given = [], {t["thesis_id"] for t in ctx.theses}
    for i, it in enumerate(ins.get("bank_view") or []):
        tid, t = it.get("thesis_id"), r.registry.get(it.get("thesis_id"))
        if t is None:
            out.append(issue("fabricated_bank_view", "bank_view", f"Тезиса {tid} нет в реестре ЦМИ — удалите пункт", i))
            continue
        if t["status"] != "current":
            repl = f", заменён {t['superseded_by']}" if t.get("superseded_by") else ""
            out.append(issue("stale_bank_view", "bank_view", f"Тезис {tid} неактуален (status={t['status']}{repl})", i))
            continue
        if tid not in given:
            out.append(issue("invalid_source", "bank_view", f"Тезис {tid} не передавался в контекст — используйте только тезисы из блока «Позиция ЦМИ»", i))
        if it.get("report_date") and it["report_date"] != t["report_date"]:
            out.append(issue("invalid_source", "bank_view", f"Дата отчёта для {tid} — {t['report_date']}, а не {it['report_date']}", i))
        ref_text, text = " ".join([t["thesis"], t.get("forecast") or "", t["quote"]]), it.get("text", "")
        if overlap(text, ref_text) < 0.3:
            out.append(issue("fabricated_bank_view", "bank_view", f"Текст не совпадает по смыслу с тезисом {tid}: «{t['thesis'][:160]}»", i))
        if extra := numbers(text) - numbers(ref_text):
            out.append(issue("fabricated_bank_view", "bank_view", f"Цифр {sorted(extra)} нет в тезисе {tid}", i))
        if new := periods(text) - periods(ref_text):
            out.append(issue("fabricated_bank_view", "bank_view", f"В тезисе {tid} нет сроков {sorted(new)} — не приписывайте банку даты, которых нет в отчёте", i))
    return out


def _check_ai_item(f: str, i: int, it: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет один вывод AI на ссылки, персонализацию и цифры"""
    out, refs_ = [], it.get("based_on") or []
    if bad := _bad_refs(refs_, ctx.catalog):
        out.append(issue("invalid_source", f, f"Несуществующие ссылки {bad}", i))
    if not any(x.startswith(("feature:", "cp:")) for x in refs_):
        out.append(issue("no_personalization", f, "Добавьте опору на признак компании (feature:…) или контрагентов (cp:…)",
                         i, "major" if f == "ai_conclusions" else "minor"))
    if f == "ai_conclusions" and it.get("confidence") not in ("medium", "low"):
        src = " ".join([ctx.news_texts.get(x, "") for x in refs_] + [ctx.vars.get("portrait", ""), ctx.vars.get("counterparties", "")]
                       + [r.registry[x]["thesis"] + " " + (r.registry[x].get("forecast") or "") for x in refs_ if x in r.registry])
        if extra := numbers(it.get("text", "")) - numbers(src):
            out.append(issue("wrong_fact", f, f"Цифры {sorted(extra)} не из источников при confidence=high; дайте диапазон и снизьте уверенность", i, "major"))
    return out


def _check_impact(ins: dict, ctx: Context) -> list[dict]:
    """Проверяет оценку влияния для высокой значимости"""
    imp = ins.get("impact") or {}
    est = imp.get("estimate")
    out = []
    if ins.get("materiality") == "high" and not est and not (imp.get("no_estimate_reason") or "").strip():
        out.append(issue("no_impact_estimate", "impact", "materiality=high: дайте impact.estimate (метрика, диапазон, метод, ссылки) или no_estimate_reason"))
    if est and (bad := _bad_refs(est.get("based_on"), ctx.catalog)):
        out.append(issue("invalid_source", "impact", f"Несуществующие ссылки в оценке {bad}"))
    return out


def _check_basis(ins: dict) -> list[dict]:
    """Проверяет, что основание карточки совпадает с наличием позиции банка"""
    basis, has_bank = ins.get("source_basis"), bool(ins.get("bank_view"))
    if basis and not has_bank and basis != "external_only":
        return [issue("basis_mismatch", "source_basis", "bank_view пуст — source_basis должен быть external_only")]
    if basis == "external_only" and has_bank:
        return [issue("basis_mismatch", "source_basis", "В карточке есть позиция ЦМИ — source_basis не может быть external_only")]
    return []


def _check_conclusions(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет выводы, гипотезы и оценку влияния"""
    out = [x for f in AI_FIELDS for i, it in enumerate(ins.get(f) or []) for x in _check_ai_item(f, i, it, ctx, r)]
    out += [issue("invalid_source", "hypotheses", f"Несуществующие ссылки {bad}", i)
            for i, it in enumerate(ins.get("hypotheses") or []) if (bad := _bad_refs(it.get("based_on"), ctx.catalog))]
    return out + _check_impact(ins, ctx) + _check_basis(ins)


def _known_feature(feat: str, catalog: dict) -> bool:
    """Проверяет, что признак из why_relevant был в контексте"""
    return (f"feature:{feat}" in catalog or f"cp:{feat}" in catalog or feat.startswith("cp:")
            or feat in ("counterparties", "MAINOKVED_CODE"))


def _factor_count(ins: dict, r: Refs) -> int:
    """Считает, со сколькими факторами связана карточка"""
    anchors = {w.get("factor") for w in ins.get("why_relevant") or []} - {None}
    for b in ins.get("bank_view") or []:
        anchors |= set(r.registry.get(b.get("thesis_id"), {}).get("factors", []))
    uses_cp = any(x.startswith("cp:") for f in AI_FIELDS for it in ins.get(f) or [] for x in it.get("based_on") or [])
    return len(anchors) + uses_cp


def _retelling(ins: dict, ctx: Context) -> list[dict]:
    """Находит заголовок и выводы, которые пересказывают новость"""
    out = []
    title = ctx.case.get("event", {}).get("title", "")
    if title and jaccard(ins.get("headline", ""), title) >= 0.6:
        out.append(issue("retelling", "headline", "Заголовок повторяет новость; сформулируйте последствие для компании"))
    for i, it in enumerate(ins.get("ai_conclusions") or []):
        ref = next((ref for ref, txt in ctx.news_texts.items() if jaccard(it.get("text", ""), txt.split("\n", 1)[-1][:400]) >= 0.55), None)
        if ref:
            out.append(issue("retelling", "ai_conclusions", f"Вывод почти дословно повторяет {ref}", i))
    return out


def _check_relevance(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет связь с компанией и отсутствие пересказа"""
    out = [issue("invalid_source", "why_relevant", f"Признак {it.get('feature', '')} не передавался в контекст", i, "major")
           for i, it in enumerate(ins.get("why_relevant") or []) if not _known_feature(it.get("feature", ""), ctx.catalog)]
    if _factor_count(ins, r) < 2:
        out.append(issue("single_factor", "ai_conclusions", "Свяжите событие хотя бы с ещё одним фактором: признаком компании, контрагентами или позицией ЦМИ"))
    return out + _retelling(ins, ctx)


def _check_actions(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет, что продукт банка один и разрешён правилом"""
    out, allowed = [], {a["id"]: a for a in ctx.allowed_actions}
    actions = ins.get("actions") or []
    if sum(a.get("type") == "bank_product" for a in actions) > 1:
        out.append(issue("too_many_products", "actions", "Не больше одного продукта банка на карточку: цель — польза для клиента, не продажа"))
    for i, a in enumerate(actions):
        product = a.get("type") == "bank_product"
        if product and not a.get("cta"):
            out.append(issue("wrong_product", "actions", "У продукта банка должен быть cta (contact_manager, request или callback)", i, "minor"))
        if not product and a.get("cta"):
            out.append(issue("wrong_product", "actions", "cta заполняется только у type=bank_product", i, "minor"))
        if not product and a.get("product"):
            out.append(issue("wrong_product", "actions", "product заполняется только у type=bank_product", i, "minor"))
        if product and (rid := a.get("rule_id")) not in allowed:
            out.append(issue("wrong_product", "actions", f"Продукт банка без сработавшего правила (rule_id={rid}); разрешены: {sorted(allowed) or 'нет'}", i))
        elif product and (a.get("product") or None) != (allowed[rid]["product"] or None):
            out.append(issue("wrong_product", "actions", f"Для {rid} продукт — «{allowed[rid]['product']}»", i))
    return out


def _check_style_and_safety(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет стиль, длину, личные данные и следы инъекций"""
    out = []
    if len(ins.get("headline", "")) > r.limits.get("headline", 90):
        out.append(issue("too_long", "headline", f"Заголовок длиннее {r.limits.get('headline', 90)} символов"))
    for f, i, txt in iter_texts(ins):
        low = txt.lower()
        out += [issue("forbidden_phrase", f, f"Уберите фразу «{ph}» — замените конкретикой", i) for ph in r.forbidden if ph in low]
        if f not in ("headline", "open_questions") and sentences(txt) > r.limits.get("item_sentences", 3):
            out.append(issue("too_long", f, f"Не больше {r.limits.get('item_sentences', 3)} предложений в пункте", i))
        if f not in ("bank_view", "open_questions") and _BANK_VOICE.search(txt):
            out.append(issue("misleading", f, "Вывод AI подан как мнение банка; позиция банка — только в bank_view по тезису ЦМИ", i))
        what = next((w for rx, w in PII if rx.search(txt)), None)
        if what:
            out.append(issue("sensitive_data", f, f"В тексте {what}; используйте доли и диапазоны", i))
    blob = to_json(ins).lower()
    out += [issue("injection_followed", "(root)", f"В карточку попала инструкция из статьи: «{h}»")
            for h in ctx.injection_hits if h.lower() in blob]
    return out


def _check_role(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Проверяет, что карточка написана для роли пользователя"""
    return [issue("wrong_role", "role", f"role должен быть «{ctx.role}»")] if ins.get("role") and ins["role"] != ctx.role else []


INSIGHT_CHECKS = (_check_role, _check_facts, _check_bank_view, _check_conclusions, _check_relevance, _check_actions,
                  _check_style_and_safety)


def check_insight(ins: dict, ctx: Context, r: Refs) -> list[dict]:
    """Выполняет все проверки карточки без модели"""
    out = validate_schema(ins, r.schemas["insight"])
    if any(i["field"] == "(root)" for i in out):
        return out
    return out + [x for check in INSIGHT_CHECKS for x in check(ins, ctx, r)]


def precheck(ins: dict | None, ctx: Context, r: Refs, parse_error: str | None = None) -> dict:
    """Готовит итог автопроверки для критика"""
    issues = [issue("schema", "(root)", parse_error or "нет JSON")] if parse_error or ins is None else check_insight(ins, ctx, r)
    need = []
    primary = primary_factor(ctx.case.get("event", {}))
    if primary and not ctx.theses:
        need.append({"tool": "search_alfa_research", "args": {"factor": primary}, "why": "нет тезисов ЦМИ по основному фактору"})
    if any(i["type"] == "single_factor" for i in issues) and not any(k.startswith("cp:") for k in ctx.catalog):
        need.append({"tool": "get_counterparties", "args": {"direction": "all"}, "why": "нужен второй фактор через контрагентов"})
    return {"pass": not with_severity(issues, "blocker", "major"), "issues": issues, "need_more_data": need[:2]}


def merge_verdicts(pre: dict, llm: dict | None) -> dict:
    """Объединяет автопроверку и мнение критика"""
    if not llm:
        return {**pre, "scores": None}
    seen = {(i["type"], i["field"], i.get("item_index")) for i in pre["issues"]}
    issues = pre["issues"] + [i for i in llm.get("issues", []) if (i["type"], i["field"], i.get("item_index")) not in seen]
    need = pre["need_more_data"] + [n for n in llm.get("need_more_data", []) if n not in pre["need_more_data"]]
    return {"pass": bool(llm.get("pass")) and not with_severity(issues, "blocker", "major"),
            "issues": issues, "need_more_data": need[:2], "scores": llm.get("scores")}


def grounding(ins: dict, ctx: Context) -> dict:
    """Считает долю пунктов с источниками и долю выводов с опорой на данные компании"""
    items = [(f, it) for f in ("what_happened", "bank_view", "hypotheses", *AI_FIELDS) for it in ins.get(f) or []]
    refs_of = [(f, it.get("source_ids") or it.get("based_on") or [it.get("thesis_id")]) for f, it in items]
    concl = [x for f, x in refs_of if f in AI_FIELDS]
    return {"grounded_share": round(sum(all(x in ctx.catalog for x in rs) for _, rs in refs_of) / len(refs_of), 3) if refs_of else 0.0,
            "personalized_share": round(sum(any(str(x).startswith(("feature:", "cp:")) for x in rs) for rs in concl) / len(concl), 3)
            if concl else 0.0}


def ui_notes(basis: str | None, r: Refs) -> dict:
    """Подбирает дисклеймер и бейдж для интерфейса"""
    d = r.disclaimers
    badge = d.get("badge", {}).get(basis or "")
    return {"disclaimer": d["always"], "basis_note": d["by_basis"].get(basis or "no_data", ""), "badge": badge,
            "not_bank_position": badge is not None, "labels": d["labels"]}


def finalize_card(ins: dict, role: str, r: Refs) -> dict:
    """Ставит в карточку роль, бейдж и дисклеймер"""
    out = dict(ins, role=role)
    if not out.get("bank_view"):
        out["source_basis"] = "external_only"
    notes = ui_notes(out.get("source_basis"), r)
    out["badge"] = notes["badge"]
    out["disclaimer"] = " ".join(x for x in (notes["disclaimer"], notes["basis_note"]) if x)
    return out


def api_errors(ins: dict, r: Refs) -> list[dict]:
    """Строго проверяет карточку перед отправкой в API"""
    out = validate_schema(ins, r.schemas["insight"])
    external = ins.get("source_basis") == "external_only"
    if external and ins.get("badge") != r.disclaimers["badge"]["external_only"]:
        out.append(issue("misleading", "badge", "Карточка без поддержки ЦМИ должна нести бейдж «Не является позицией банка»"))
    if not external and ins.get("badge"):
        out.append(issue("misleading", "badge", "Бейдж ставится только при source_basis = external_only"))
    if r.disclaimers["always"] not in (ins.get("disclaimer") or ""):
        out.append(issue("misleading", "disclaimer", "Нет дисклеймера «не является инвестиционной рекомендацией»"))
    return out


def check_digest(obj: dict, cards: list[dict], r: Refs) -> list[dict]:
    """Проверяет сводку P14"""
    out = validate_schema(obj, r.schemas["digest"])
    if out:
        return out
    card_ids = {c["card_id"] for c in cards}
    known = card_ids | {b["thesis_id"] for c in cards for b in c["insight"].get("bank_view") or []}
    out += [issue("invalid_source", "top", f"Карточки {t['card_id']} нет в списке", i) for i, t in enumerate(obj["top"]) if t["card_id"] not in card_ids]
    for i, w in enumerate(obj["watch"]):
        if bad := [x for x in w["source_ids"] if x not in known]:
            out.append(issue("invalid_source", "watch", f"Несуществующие ссылки {bad}", i))
    return out
