from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database.models import Payment


class PaymentsRepo:
    def __init__(self, session: Session):
        self.session = session

    def for_company(self, company_id: str, limit: int = 1000) -> list[Payment]:
        """Все платежи, где компания связана"""
        stmt = (
            select(Payment)
            .where((Payment.payer_id == company_id) | (Payment.beneficiary_id == company_id))
            .order_by(Payment.pay_amt.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def total_amt(self, payer_id: str, beneficiary_id: str) -> float:
        """Сумма платежей между двумя компаниями."""

        stmt = select(func.sum(Payment.pay_amt)).where(
            Payment.payer_id == payer_id,
            Payment.beneficiary_id == beneficiary_id,
        )
        return self.session.scalar(stmt) or 0.0

    def count(self) -> int:
        return self.session.scalar(select(func.count(Payment.id))) or 0
