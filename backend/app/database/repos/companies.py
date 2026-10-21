from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database.models import Company, CompanyLink


class CompaniesRepo:
    def __init__(self, session: Session):
        self.session = session

    def get(self, company_id: str) -> Company | None:
        return self.session.get(Company, company_id)

    def get_many(self, ids: list[str]) -> list[Company]:
        """Несколько компаний по списку ID."""
        if not ids:
            return []

        stmt = select(Company).where(Company.id.in_(ids))
        return list(self.session.scalars(stmt).all())

    def list(
            self,
            client_type: str | None = None,
            min_revenue: float | None = None,
            region: str | None = None,
            okved_prefix: str | None = None,
            okved_name_prefix: str | None = None,
            limit: int = 100,
    ) -> list[Company]:
        """Список компаний. Все параметры — опциональные фильтры.

        Без параметров — топ-100 по выручке.
        """
        stmt = select(Company)

        if client_type:
            stmt = stmt.where(Company.client_type == client_type)
        if min_revenue is not None:
            stmt = stmt.where(Company.revenue >= min_revenue)
        if region:
            stmt = stmt.where(Company.region == region)
        if okved_prefix:
            stmt = stmt.where(Company.okved_code.startswith(okved_prefix))
        if okved_name_prefix:
            stmt = stmt.where(Company.okved_name.startswith(okved_name_prefix))

        stmt = stmt.order_by(Company.revenue.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())

    def get_links(
            self,
            company_id: str,
            direction: str | None = None,
            min_weight: float = 0.0,
            limit: int = 50,
    ) -> list[CompanyLink]:
        """Связи компании из графа."""
        stmt = select(CompanyLink).where(
            (CompanyLink.src_id == company_id) | (CompanyLink.dst_id == company_id)
        )

        if min_weight > 0:
            stmt = stmt.where(CompanyLink.weight >= min_weight)
        if direction == "buyer":
            stmt = stmt.where(CompanyLink.dst_id == company_id)
        elif direction == "supplier":
            stmt = stmt.where(CompanyLink.src_id == company_id)

        stmt = stmt.order_by(CompanyLink.weight.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(self) -> int:
        return self.session.query(Company).count()
