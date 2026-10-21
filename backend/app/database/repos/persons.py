from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.database.models import Person


class PersonsRepo:
    def __init__(self, session: Session):
        self.session = session

    def get_by_company(self, company_id: str) -> list[Person]:
        """Физлица, связанные с компанией."""
        stmt = select(Person).where(Person.synthetic_u == company_id)
        return list(self.session.scalars(stmt).all())

    def get_companies_by_person(self, synthetic_f: str) -> list[str]:
        """ID компаний, связанных с физлицом."""
        stmt = select(Person.synthetic_u).where(Person.synthetic_f == synthetic_f)
        return list(self.session.scalars(stmt).all())

    def count(self) -> int:
        return self.session.scalar(select(func.count(Person.id))) or 0
