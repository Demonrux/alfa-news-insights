from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import uuid

from backend.app.database.database import Database

app = FastAPI(title="Alfa News Insights API")


class LoginRequest(BaseModel):
    person_id: str


class CompanyInfo(BaseModel):
    id: str
    name: str
    revenue: float


class FeedItem(BaseModel):
    event_id: str
    headline: str
    impact: str
    materiality: float
    date: str
    why_relevant: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(req: LoginRequest):
    """ Авторизация по ID физлица. Возвращает токен и список доступных компаний."""
    with Database() as db:
        companies_ids = db.persons.get_companies_by_person(req.person_id)
        if not companies_ids:
            raise HTTPException(status_code=404, detail="Физлицо не найдено или нет доступа к компаниям")

        companies = []
        for cid in companies_ids:
            c = db.companies.get(cid)
            if c:
                companies.append({
                    "id": c.id,
                    "name": c.okved_name[:40],
                    "revenue": c.revenue
                })

    return {
        "token": f"mock-token-{uuid.uuid4().hex[:8]}",
        "person_id": req.person_id,
        "companies": companies
    }


@app.get("/api/feed")
def get_feed(client_id: str):
    """Возвращает ленту инсайтов для компании кдиента (пока что мок)"""
    return [
        {
            "event_id": "mock-event-1",
            "headline": "Сохранение ключевой ставки на уровне 14%",
            "impact": "negative",
            "materiality": 0.85,
            "date": "2026-10-22",
            "why_relevant": "Компания использует кредитные продукты (LOA), высокая ставка давит на маржинальность."
        },
        {
            "event_id": "mock-event-2",
            "headline": "ЕС утвердил 22-й пакет санкций",
            "impact": "mixed",
            "materiality": 0.72,
            "date": "2026-10-21",
            "why_relevant": "У компании есть экспорт в недружественные страны (FTS_FLAG=1), возможны логистические риски."
        }
    ]