from backend.app.database.session import Base, engine, session_scope, SessionLocal
from backend.app.database.repos.companies import CompaniesRepo
from backend.app.database.repos.persons import PersonsRepo
from backend.app.database.repos.payments import PaymentsRepo
from backend.app.database.repos.news import NewsRepo
from backend.app.database.repos.events import EventsRepo


class Database:
    """Фасад над репозиториями"""

    @property
    def companies(self) -> CompaniesRepo:
        return CompaniesRepo(SessionLocal())

    @property
    def persons(self) -> PersonsRepo:
        return PersonsRepo(SessionLocal())

    @property
    def payments(self) -> PaymentsRepo:
        return PaymentsRepo(SessionLocal())

    @property
    def news(self) -> NewsRepo:
        return NewsRepo(SessionLocal())

    @property
    def events(self) -> EventsRepo:
        return EventsRepo(SessionLocal())

    @property
    def transaction(self):
        """Контекст для батч-операций в одной транзакции."""
        return session_scope()

    @staticmethod
    def create_all() -> None:
        """Создать все таблицы (по моделям из models.py)."""

        Base.metadata.create_all(bind=engine)

    @staticmethod
    def drop_all() -> None:
        """Снести все таблицы"""
        Base.metadata.drop_all(bind=engine)
