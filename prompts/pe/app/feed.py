from __future__ import annotations

from pathlib import Path

from ..domain import checks
from ..domain.company import relevance_items
from ..domain.model import Refs
from ..domain.text import to_json
from ..infra.repo import CASES, load_cases, refs, render_template
from .context import theses_block

_ORDER = {"high": 0, "medium": 1, "low": 2}


def not_relevant_text(factors: list[str]) -> str:
    """Объясняет, почему новость не показана клиенту"""
    return render_template("not_relevant.j2", factors=factors)


def why_line(components: list[dict], r: Refs | None = None) -> str:
    """Пишет строку для ленты о том, почему клиент видит новость, до генерации карточки"""
    return " · ".join(f"{it['factor_name']}: {it['explanation']}" for it in relevance_items(components, r or refs())[:3])


def digest_vars(cards: list[dict], role: str, period: str, today: str, r: Refs | None = None,
                user_title: str | None = None) -> dict:
    """Готовит данные для сводки по всем компаниям пользователя"""
    r = r or refs()
    lines = []
    for c in sorted(cards, key=lambda c: _ORDER.get(c["insight"].get("materiality"), 3)):
        ins = c["insight"]
        concl = (ins.get("ai_conclusions") or [{}])[0].get("text", "")
        th = ", ".join(b["thesis_id"] for b in ins.get("bank_view") or []) or "нет"
        lines.append(f"- {c['card_id']} | компания: {c.get('company', '—')} | влияние: {ins.get('overall_impact')}, "
                     f"{ins.get('materiality')} | {ins.get('headline')} | главный вывод: {concl} | тезисы ЦМИ: {th}")
    ids = sorted({b["thesis_id"] for c in cards for b in c["insight"].get("bank_view") or []})
    return {"role": role, "role_block": r.role_block(role, user_title), "period": period, "today": today, "cards_block": "\n".join(lines),
            "theses_block": theses_block([r.registry[t] for t in ids if t in r.registry]), "style_block": r.style}


def export_examples(out_dir: str | Path) -> list[Path]:
    """Сохраняет примеры карточек и список ролей для фронта и бэка"""
    r, out = refs(), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / "roles.json"]
    paths[0].write_text(to_json(r.role_names, pretty=True), encoding="utf-8")
    for case in load_cases(CASES / "p5_cases.yaml"):
        ins = case["reference"]
        path = out / f"{case['id']}.json"
        path.write_text(to_json({"insight": ins, "ui": checks.ui_notes(ins.get("source_basis"), r)}, pretty=True),
                        encoding="utf-8")
        paths.append(path)
    return paths

