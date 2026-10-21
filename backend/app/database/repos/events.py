from sqlalchemy.orm import Session
from backend.app.database.models import Event


class EventsRepo:
    def __init__(self, session: Session):
        self.session = session

    def get(self, event_id: str) -> Event | None:
        return self.session.get(Event, event_id)

    def get_by_news(self, news_id: str) -> Event | None:
        """Событие, обогащённое из конкретной новости."""

        return self.session.query(Event).filter(Event.news_id == news_id).first()

    def list(
            self,
            event_type: str | None = None,
            entity: str | None = None,
            limit: int = 100,
    ) -> list[Event]:
        """Список событий. Все параметры — опциональные фильтры.

        :param event_type: тип события ("sanctions", "contract", ...).
        :param entity: приблизительный поиск по подстроке в entities``
            (LIKE %"{entity}"%). В Postgres переедет на jsonb .

        :param limit: максимум записей (свежие — первыми).

        :return: список Event.
        """
        q = self.session.query(Event)
        if event_type:
            q = q.filter(Event.event_type == event_type)
        if entity:
            q = q.filter(Event.entities.cast(str).like(f'%"{entity}"%'))
        return q.order_by(Event.created_at.desc()).limit(limit).all()

    def save(self, news_id: str, data: dict) -> Event:
        """Сохранить Event из JSON-ответа LLM.

        :param news_id: ID новости (Event.news_id).
        :param data: словарь с ключами event_type, entities,
            sentiment, confidence, input_quality, reasoning.

        :return: созданный Event.
        """
        event = Event(
            news_id=news_id,
            event_type=data["event_type"],
            entities=data.get("entities", [])[:10],
            sentiment=data.get("sentiment", "neutral"),
            confidence=float(data.get("confidence", 0.5)),
            input_quality=data.get("input_quality", "full"),
            reasoning=(data.get("reasoning") or "")[:500],
        )

        self.session.add(event)
        self.session.commit()
        return event

    def count(self) -> int:
        return self.session.query(Event).count()

    def count_by_type(self) -> dict[str, int]:
        """Сколько событий каждого типа: {event_type: count}."""

        from sqlalchemy import func
        rows = (
            self.session.query(Event.event_type, func.count(Event.id))
            .group_by(Event.event_type)
            .all()
        )

        return {et: n for et, n in rows}
