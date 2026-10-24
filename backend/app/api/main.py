import base64
import threading
import hashlib
from datetime import date, datetime
import logging
logger = logging.getLogger("uvicorn.error")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.database.database import Database
from backend.app.database.models import News, Company, CompanyLink

from llm.agent import (
    run_insight_pipeline,
    Trace,
    NotRelevant,
    InsightRejected,
    PipelineError,
)
from llm.agent.planner import classify, relevance
from llm.agent.trace import Trace as AgentTrace
from prompts.pe.domain.model import NotEligible, primary_factor
from prompts.pe.infra import llm as pe_llm
from prompts.pe.infra.llm import BudgetExceeded
from prompts.pe.infra.repo import refs
from backend.app.api.cards import router as cards_router


app = FastAPI(title="Alfa News Insights API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards_router, prefix="/api")


def mask_id(real_id: str) -> str:
    return f"comp_{base64.urlsafe_b64encode(real_id.encode()).decode()}"


def unmask_id(masked_id: str) -> str:
    return base64.urlsafe_b64decode(masked_id.replace("comp_", "").encode()).decode()


def _news_key_for_feed(title: str, body: str) -> str:
    return hashlib.sha1((title + body).encode("utf-8")).hexdigest()[:16]


FEED_EVENT_CACHE: dict[str, dict] = {}
_FEED_CALLER = None


def _feed_caller():
    """Ленивая инициализация LLM-клиента, один на процесс."""
    global _FEED_CALLER
    if _FEED_CALLER is None:
        _FEED_CALLER = pe_llm.live_caller()
    return _FEED_CALLER


def _safe_trace(trace) -> list[dict]:
    """Сериализует шаги агента для фронта: [{title, detail}]."""
    steps = getattr(trace, "steps", []) or []
    out: list[dict] = []
    for step in steps:
        title = step.get("name") or step.get("kind") or "step"
        detail = (
            step.get("result_preview")
            or step.get("prompt")
            or step.get("reason")
            or step.get("stage")
            or ""
        )
        out.append({"title": str(title), "detail": str(detail)[:500]})
    return out


def _company_row(company: Company) -> dict:
    pj = company.profile_json or {}
    row = {
        "id": company.id,
        "okved_code": company.okved_code,
        "okved_name": company.okved_name,
        "MAINOKVED_CODE": company.okved_code,
        "MAINOKVED_NAME": company.okved_name,
        "REVENUE_COMPANY": company.revenue,
        "REGION": company.region,
        "CITY": company.city,
        "CL_TYPE": company.client_type,
        "revenue": company.revenue,
        "region": company.region,
        "city": company.city,
        "profile_json": pj,
    }
    row.update(pj)
    return row


def _counterparties(db: Database, company: Company) -> list[dict]:
    """Контрагенты компании по графу платежей с долями."""
    links = db.companies.get_links(company.id, limit=50)
    total = sum(float((l.meta or {}).get("pay_amt", 0)) for l in links) or 1.0
    out: list[dict] = []
    for link in links:
        other_id = link.dst_id if link.src_id == company.id else link.src_id
        other = db.companies.get(other_id)
        if not other:
            continue
        out.append({
            "id": other.id,
            "okved": other.okved_code,
            "okved_name": other.okved_name,
            "direction": "supplier" if link.src_id == company.id else "buyer",
            "share": float((link.meta or {}).get("pay_amt", 0)) / total,
            "link_type": link.link_type,
        })
    return out


class LoginRequest(BaseModel):
    person_id: str


class InsightRequest(BaseModel):
    event_id: str
    company_id: str
    role: str = "cfo"


def _start_warm():
    """Фоновый прогрев FEED_EVENT_CACHE."""
    def _run():
        try:
            with Database() as db:
                news_list = db.news.recent(days=30, limit=15)
                if not news_list:
                    news_list = db.news.recent(days=3650, limit=15)
                if not news_list:
                    logger.warning("[feed] warm: no news")
                    return
                r = refs()
                caller = _feed_caller()
                today = date.today().isoformat()
                ok = fail = 0
                for i, n in enumerate(news_list, 1):
                    try:
                        classify(
                            {"id": n.id, "title": n.title, "text": n.body, "source": n.source},
                            caller, AgentTrace(), r, today, cache=FEED_EVENT_CACHE,
                        )
                        ok += 1
                        logger.warning(f"[feed] warm {i}/{len(news_list)} ok")
                    except Exception as e:
                        fail += 1
                        logger.warning(
                            f"[feed] warm {i}/{len(news_list)} FAIL "
                            f"{type(e).__name__}: {str(e)[:80]}"
                        )
                logger.warning(f"[feed] warmed {len(FEED_EVENT_CACHE)} events (ok={ok} fail={fail})")
        except Exception as e:
            logger.warning(f"[feed] warm failed: {type(e).__name__}: {e}")
    threading.Thread(target=_run, daemon=True, name="feed-warm").start()


@app.on_event("startup")
def _warm_feed():
    _start_warm()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(req: LoginRequest):
    with Database() as db:
        companies_ids = db.persons.get_companies_by_person(req.person_id)
        if not companies_ids:
            raise HTTPException(404, "Физлицо не найдено")

        companies = []
        for cid in companies_ids:
            c = db.companies.get(cid)
            if c:
                companies.append({
                    "id": mask_id(c.id),
                    "short": c.id[:2],
                    "name": f"Компания {c.id[-3:]}",
                    "label": f"{(c.okved_name or 'Отрасль')[:20]} · Группа",
                    "activity": c.okved_name or "Деятельность",
                    "group": "Группа 1",
                    "newEvents": 3,
                })

    return {
        "person": {"fullName": "Иван Иванович Иванов", "initials": "ИИ"},
        "lastCompanyId": companies[0]["id"] if companies else None,
        "companies": companies,
    }


@app.get("/api/feed")
def get_feed(client_id: str, role: str = "cfo"):
    real_id = unmask_id(client_id)
    with Database() as db:
        company = db.companies.get(real_id)
        if not company:
            raise HTTPException(404, "Компания не найдена")

        news_list = db.news.recent(days=30, limit=25)
        if not news_list:
            news_list = db.news.recent(days=3650, limit=25)

        r = refs()
        row = _company_row(company)
        cps = _counterparties(db, company)
        items: list[dict] = []
        not_ready = 0

        for n in news_list:
            key = _news_key_for_feed(n.title or "", n.body or "")
            event = FEED_EVENT_CACHE.get(key)
            if event is None:
                not_ready += 1
                continue

            components = relevance(row, event, cps, r)
            if not components:
                continue

            top = components[0]
            contrib = float(top.get("contribution", 0))
            materiality = (
                "high" if contrib >= 0.7
                else "medium" if contrib >= 0.4
                else "low"
            )
            factor = primary_factor(event)
            sentiment = event.get("sentiment") or "neutral"
            impact = {"negative": "negative", "positive": "positive"}.get(sentiment, "neutral")
            items.append({
                "id": n.id,
                "headline": n.title,
                "overallImpact": impact,
                "materiality": materiality,
                "factor": factor,
                "createdAt": n.published_at.isoformat() if n.published_at else datetime.utcnow().isoformat(),
                "isNew": bool(n.published_at and (datetime.utcnow() - n.published_at).days < 3),
                "external": n.source not in ("cbr", "prime"),
                "whyLine": top.get("explanation") or f"Фактор: {r.factor_names.get(factor, factor)}",
                "sourceLine": f"{n.source} · {n.published_at:%d.%m.%Y}" if n.published_at else n.source,
            })

        items.sort(
            key=lambda x: ({"high": 3, "medium": 2, "low": 1}[x["materiality"]], x["createdAt"]),
            reverse=True,
        )

        logger.warning(f"[feed] company={real_id} role={role} total={len(news_list)} cached={len(items)} not_ready={not_ready}")

        return items[:15]


@app.post("/api/insights")
def generate_insight(req: InsightRequest):
    real_company_id = unmask_id(req.company_id)

    with Database() as db:
        news = db.news.get(req.event_id)
        if not news:
            raise HTTPException(404, "Новость не найдена")

        company = db.companies.get(real_company_id)
        if not company:
            raise HTTPException(404, "Компания не найдена")

        pj = company.profile_json or {}

        products_map = {
            "CL_PRODUCT_RKO_MARK": "РКО",
            "CL_PRODUCT_GAR_MARK": "Гарантии",
            "CL_PRODUCT_LOA_MARK": "Кредиты",
            "CL_PRODUCT_LEA_MARK": "Лизинг",
            "CL_PRODUCT_DEP_MARK": "Депозиты",
            "CL_PRODUCT_ZPP_MARK": "Зарплатный проект",
            "FACTORING_MARK": "Факторинг",
        }
        products_yes = [
            name for key, name in products_map.items() if pj.get(key) == 1.0
        ]
        products_no = [
            name for key, name in products_map.items() if pj.get(key) != 1.0
        ]

        fts_line = None
        if pj.get("FTS_FLAG") == 1.0:
            country = pj.get("FTS_COUNTRY_NAME")
            fts_line = (
                f"ВЭД: есть (страна: {country})" if country else "ВЭД: есть"
            )

        rev = company.revenue or 0
        rev_band = (
            "> 50 млрд" if rev >= 50e9
            else "15-50 млрд" if rev >= 15e9
            else "2-15 млрд"
        )

        company_data = _company_row(company)
        company_data.update({
            "revenue_band": rev_band,
            "workers": pj.get("AMOUNT_WORKERS_FNS_GRADATION"),
            "age": pj.get("COMPANY_AGE_YEARS_GRADATION"),
            "eco_stage": pj.get("ECO_MARK_LABEL"),
            "org_line": (
                f"Форма собственности: {pj.get('OKFS_NAME')}"
                if pj.get("OKFS_NAME") else None
            ),
            "products_yes": products_yes,
            "products_no": products_no,
            "fts_line": fts_line,
            "group_line": (
                f"Группа: {company.group_id}"
                if company.group_id else None
            ),
            "counterparties": _counterparties(db, company),
        })

        news_item = {
            "id": news.id,
            "title": news.title,
            "text": news.body,
            "source": news.source,
            "date": (
                news.published_at.isoformat()
                if news.published_at else None
            ),
        }

    trace = Trace()
    try:
        card = run_insight_pipeline(
            company_data, news_item, role=req.role, trace=trace,
        )

        if not card:
            raise NotRelevant("Пустая карточка")

        return {
            "id": req.event_id,
            "companyId": req.company_id,
            "createdAt": datetime.utcnow().isoformat(),
            "isNew": True,
            "primaryFactor": (
                card["why_relevant"][0]["factor"]
                if card.get("why_relevant") else "KEY_RATE"
            ),
            "criticPassed": True,
            "card": card,
            "sources": {},
            "trace": _safe_trace(trace),
        }

    except NotRelevant as exc:
        logger.warning(f"[insights] NotRelevant: {exc}")
        return {
            "card": None,
            "reason": str(exc),
            "trace": _safe_trace(trace),
        }

    except NotEligible as exc:
        raise HTTPException(403, str(exc))

    except BudgetExceeded as exc:
        raise HTTPException(429, str(exc))

    except (InsightRejected, PipelineError) as exc:
        logger.warning(
            f"[insights] rejected {type(exc).__name__}: {exc} | "
            f"issues={exc.details.get('issues', [])[:3]}"
        )
        raise HTTPException(
            422,
            detail={
                "reason": str(exc),
                "issues": exc.details.get("issues", []),
            },
        )

    except (InsightRejected, PipelineError) as exc:
        logger.warning(f"[insights] rejected {type(exc).__name__}: {exc}")
        raise HTTPException(422, detail={...})

    except Exception as exc:
        logger.error(f"[insights] unhandled {type(exc).__name__}: {exc}", exc_info=True)
        raise HTTPException(500, f"Internal error: {type(exc).__name__}: {str(exc)}")