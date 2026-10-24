"""Прогон полного пайплайна для одной новости с traceback."""
import traceback

from backend.app.database.database import Database
from backend.app.api.main import _company_row, _counterparties
from llm.agent import run_insight_pipeline, Trace

NEWS_ID = "0ff25357-d070-4b8d-aac8-1dc79b7e7a86"
COMPANY_ID = "U_155903"

with Database() as db:
    n = db.news.get(NEWS_ID)
    c = db.companies.get(COMPANY_ID)
    if not n:
        print(f"news not found: {NEWS_ID}")
        raise SystemExit(1)
    if not c:
        print(f"company not found: {COMPANY_ID}")
        raise SystemExit(1)

    row = _company_row(c)
    row.update({
        "revenue_band": "2-15 млрд",
        "products_yes": [],
        "products_no": [],
        "fts_line": None,
        "org_line": None,
        "workers": None,
        "age": None,
        "eco_stage": None,
        "group_line": None,
        "counterparties": _counterparties(db, c),
    })
    news_item = {
        "id": n.id,
        "title": n.title,
        "text": n.body,
        "source": n.source,
        "date": n.published_at.isoformat() if n.published_at else None,
    }

print(f"news: {n.title[:60]}")
trace = Trace()
try:
    card = run_insight_pipeline(row, news_item, role="ceo", trace=trace)
    headline = (card or {}).get("headline", "?")[:60]
    print(f"OK, headline: {headline}")
except Exception as e:
    print(f"EXC: {type(e).__name__}: {e}")
    traceback.print_exc()

print("---- steps ----")
for s in trace.steps:
    stage = s.get("stage", "?")
    kind = s.get("kind", "?")
    name = s.get("name", "?")
    ms = s.get("ms", "-")
    ok = s.get("ok", "-")
    print(f"{stage} {kind} {name} ms={ms} ok={ok}")