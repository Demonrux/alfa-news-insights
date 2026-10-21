from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database.models import News, Event


class NewsRepo:
    def __init__(self, session: Session):
        self.session = session

    def get(self, news_id: str) -> News | None:
        return self.session.get(News, news_id)

    def pending_for_enrichment(self, limit: int = 100) -> list[News]:
        """Новости, у которых ещё нет Event — для обогащения."""
        sub_q = select(Event.news_id)
        stmt = (
            select(News)
            .where(~News.id.in_(sub_q))
            .order_by(News.fetched_at.desc())
            .limit(limit)
        )

        return list(self.session.scalars(stmt).all())

    def recent(self, days: int = 7, limit: int = 200) -> list[News]:
        """Новости за последние N дней"""

        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(News)
            .where(News.published_at >= cutoff)
            .order_by(News.published_at.desc())
            .limit(limit)
        )

        return list(self.session.scalars(stmt).all())

    def exists_by_url(self, url: str) -> bool:
        return self.session.query(News.id).filter(News.url == url).first() is not None

    def exists_by_hash(self, raw_hash: str) -> bool:
        return self.session.query(News.id).filter(News.raw_hash == raw_hash).first() is not None

    def count(self) -> int:
        return self.session.query(News).count()
