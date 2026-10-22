from backend.app.database.session import Base, engine, SessionLocal
from backend.app.database.repos.companies import CompaniesRepo
from backend.app.database.repos.news import NewsRepo
from backend.app.database.repos.events import EventsRepo
from backend.app.database.repos.persons import PersonsRepo
from backend.app.database.repos.payments import PaymentsRepo
# from app.database.repos.insights import InsightsRepo
# from app.database.repos.trace import TraceRepo


class Database:
    """Единая точка входа в БД.

    with Database() as db:
        company = db.companies.get("U_21915")
    """

    def __init__(self):
        self._session = SessionLocal()

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def companies(self) -> CompaniesRepo:
        return CompaniesRepo(self._session)

    @property
    def news(self) -> NewsRepo:
        return NewsRepo(self._session)

    @property
    def events(self) -> EventsRepo:
        return EventsRepo(self._session)

    @property
    def persons(self) -> PersonsRepo:
        return PersonsRepo(self._session)

    @property
    def payments(self) -> PaymentsRepo:
        return PaymentsRepo(self._session)

    # Если добавили Insights и Trace
    # @property
    # def insights(self) -> InsightsRepo:
    #     return InsightsRepo(self._session)
    #
    # @property
    # def trace(self) -> TraceRepo:
    #     return TraceRepo(self._session)

    @staticmethod
    def create_all() -> None:
        from backend.app.database import models
        Base.metadata.create_all(bind=engine)

    @staticmethod
    def drop_all() -> None:
        from backend.app.database import models
        Base.metadata.drop_all(bind=engine)
