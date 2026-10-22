"""Build a small, reviewable company/news relevance set from local demo data.

Run from the repository root:
    python -m ml.build_golden_set

The labels are initial human-readable hypotheses, not production ground truth.
Review them with the domain team before using them as final evaluation labels.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "ml" / "golden_news_company.csv"

# Indices refer to the current local data/news.json snapshot. The generated
# CSV embeds the article text and raw_hash, so it remains usable on its own.
ARTICLES = [
    (26, "INFLATION"),
    (33, "KEY_RATE"),
    (141, "FX"),
    (103, "SANCTIONS_TRADE"),
    (63, "CREDIT_DEBT_MARKET"),
    (196, "INDUSTRY_EVENT"),
    (160, "LOGISTICS"),
    (146, "SANCTIONS_TRADE"),
]

COMPANY_SEARCH_CONTEXT = {
    "U_21915": "Оптовая торговля бумагой, картоном, целлюлозной продукцией, упаковкой и материалами для полиграфии.",
    "U_9748": "Оптовая торговля удобрениями, агрохимикатами, средствами для сельского хозяйства и аграрного производства.",
    "U_9250": "Инженерное строительство, инфраструктурные объекты, строительные проекты, материалы, оборудование и проектное финансирование.",
    "U_11496": "Транспортная логистика, грузоперевозки, экспедирование, фрахт, порты, маршруты и транспортные расходы.",
    "U_142420": "Оптовые поставки компьютеров, электроники, периферийной техники, комплектующих, микросхем и программного обеспечения.",
    "U_408263": "Неспециализированная оптовая торговля товарами разных категорий, закупки, товарные запасы и импорт.",
}

# Every judgment includes a short, inspectable rationale. Company IDs are
# synthetic IDs from data/demo_companies.json, not real customer identifiers.
# For each selected article the key is a synthetic company ID and the value is
# (binary relevance, relationship type, rationale).
ANNOTATIONS: dict[int, dict[str, tuple[int, str, str]]] = {
    26: {
        "U_21915": (1, "macro_cost", "Инфляционные ожидания влияют на закупочные цены и оборотный капитал оптовика бумаги."),
        "U_9748": (1, "macro_cost", "Инфляционные ожидания влияют на цены агрохимии, себестоимость и оборотный капитал."),
        "U_9250": (1, "macro_cost", "Инфляционные ожидания влияют на стоимость материалов и долгосрочных строительных проектов."),
        "U_11496": (1, "macro_cost", "Инфляционные ожидания связаны с расходами на топливо, персонал и транспортные услуги."),
        "U_142420": (1, "macro_cost", "Инфляция влияет на закупочные цены и спрос на компьютерную технику."),
        "U_408263": (1, "macro_cost", "Инфляция влияет на цены закупок и оборотный капитал универсального оптовика."),
    },
    33: {
        "U_21915": (1, "macro_financing", "Ключевая ставка влияет на стоимость кредитования и финансирование запасов."),
        "U_9748": (1, "macro_financing", "Ключевая ставка влияет на стоимость оборотного капитала и финансирование сезонных закупок."),
        "U_9250": (1, "macro_financing", "Ставка влияет на проектное финансирование и экономику долгосрочного строительства."),
        "U_11496": (1, "macro_financing", "Ставка влияет на стоимость обновления транспорта и кредитования оборотного капитала."),
        "U_142420": (1, "macro_financing", "Ставка влияет на кредитование закупок и спрос клиентов на дорогостоящую технику."),
        "U_408263": (1, "macro_financing", "Ставка влияет на стоимость запасов и финансирование оптовой торговли."),
    },
    141: {
        "U_21915": (1, "fx_supply_cost", "Изменение курса может менять рублёвую стоимость импортной бумаги и закупок."),
        "U_9748": (1, "fx_supply_cost", "Курс влияет на экспортную выручку производителей удобрений и стоимость импортных компонентов."),
        "U_9250": (1, "fx_supply_cost", "Курс влияет на стоимость импортного оборудования и материалов для строительства."),
        "U_11496": (1, "fx_supply_cost", "Курс может влиять на стоимость импортной техники, запчастей и международных перевозок."),
        "U_142420": (1, "fx_direct", "Прямая связь: компьютерная техника и комплектующие часто закупаются за валюту."),
        "U_408263": (1, "fx_supply_cost", "Курс может менять закупочную стоимость импортных товаров в универсальном опте."),
    },
    103: {
        "U_21915": (0, "none", "В новости речь об экспорте удобрений; профиль компании — оптовая торговля бумагой."),
        "U_9748": (1, "direct_industry", "Прямая отраслевая связь: компания торгует удобрениями и агрохимической продукцией."),
        "U_9250": (0, "none", "В новости речь об удобрениях, прямой связи со строительным профилем не видно."),
        "U_11496": (1, "indirect_trade", "Рост экспорта удобрений может увеличить спрос на перевозку и экспортную логистику."),
        "U_142420": (0, "none", "В новости речь об удобрениях; профиль компьютерной торговли не связан с событием."),
        "U_408263": (0, "weak_indirect", "Универсальная торговля сама по себе не подтверждает связь с рынком удобрений."),
    },
    63: {
        "U_21915": (0, "none", "Кредитный портфель застройщиков не относится напрямую к торговле бумагой."),
        "U_9748": (0, "none", "Новость о финансировании строительства жилья, а не о рынке удобрений."),
        "U_9250": (1, "direct_industry", "Прямая связь: компания строит инженерные сооружения; новость описывает кредитование застройщиков."),
        "U_11496": (0, "weak_indirect", "Возможен косвенный эффект на перевозки, но конкретной связи с компанией нет."),
        "U_142420": (0, "none", "Новость о кредитовании застройщиков не связана с компьютерной торговлей."),
        "U_408263": (0, "none", "Новость об отрасли жилищного строительства; профиль компании — неспециализированный опт."),
    },
    196: {
        "U_21915": (0, "none", "Сокращение числа строительных компаний не связано напрямую с торговлей бумагой."),
        "U_9748": (0, "none", "Новость об ухудшении ситуации в строительстве, прямой связи с удобрениями нет."),
        "U_9250": (1, "direct_industry", "Прямая связь: событие касается строительной отрасли, в которой работает компания."),
        "U_11496": (0, "weak_indirect", "Снижение активности строителей может затронуть перевозки, но это косвенная гипотеза."),
        "U_142420": (0, "none", "Новость о строительной отрасли, не о компьютерной технике."),
        "U_408263": (0, "none", "Профиль неспециализированного опта не даёт явной связи с проблемами строителей."),
    },
    160: {
        "U_21915": (0, "none", "Новость о перевозке нефти по Севморпути; явной связи с бумажным оптом нет."),
        "U_9748": (0, "weak_indirect", "Новость касается нефтяного экспорта; связь с перевозками удобрений не подтверждена."),
        "U_9250": (0, "none", "Событие об экспорте нефти по Севморпути не связано с инженерным строительством."),
        "U_11496": (1, "direct_industry", "Прямая связь с перевозками и экспортными логистическими маршрутами."),
        "U_142420": (0, "none", "Новость о нефтяной логистике, не о компьютерной торговле."),
        "U_408263": (0, "weak_indirect", "Общий профиль оптовой торговли не подтверждает связь с морской перевозкой нефти."),
    },
    146: {
        "U_21915": (0, "none", "Экспортные ограничения на редкоземельные металлы не связаны с бумажным оптом."),
        "U_9748": (0, "none", "Новость о редкоземельных металлах и компонентах, не об удобрениях."),
        "U_9250": (0, "weak_indirect", "Возможное влияние на оборудование не указано в новости и требует подтверждения."),
        "U_11496": (0, "none", "Новость о поставках редкоземельных материалов, не о транспортном рынке."),
        "U_142420": (1, "indirect_supply_chain", "Возможна связь через глобальные цепочки поставок электроники и чипов; влияние косвенное."),
        "U_408263": (0, "none", "Неспециализированный оптовый профиль не подтверждает связь с редкоземельными материалами."),
    },
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> int:
    companies = {company["id"]: company for company in _read_json(DATA / "demo_companies.json")}
    news = _read_json(DATA / "news.json")
    rows: list[dict[str, Any]] = []

    for news_index, expected_category in ARTICLES:
        article = news[news_index]
        body = article.get("body", "")
        title = article.get("title", "")
        if body.startswith(title):
            body = body[len(title):].strip(" \n—:-")
        text = " ".join((title, body[:700])).strip()
        for company_id, (relevance, relation, rationale) in ANNOTATIONS[news_index].items():
            company = companies[company_id]
            rows.append({
                "company_id": company_id,
                "company_client_type": company.get("client_type", ""),
                "company_okved": company.get("okved_name", ""),
                "company_search_context": COMPANY_SEARCH_CONTEXT[company_id],
                "company_region": company.get("region", ""),
                "news_id": article.get("raw_hash", f"local-index-{news_index}"),
                "news_source": article.get("source", ""),
                "news_published_at": article.get("published_at", ""),
                "news_title": title,
                "news_text": text,
                "relevance": relevance,
                "relation_type": relation,
                "relation_reason": rationale,
                "expected_category": expected_category,
                "annotation_status": "draft_needs_domain_review",
                "annotation_source": "initial_manual_hypothesis",
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Wrote {build()} annotated pairs to {OUTPUT}")
