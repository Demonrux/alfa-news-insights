import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, DateTime, JSON, ForeignKey, Boolean
from app.database.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Company(Base):
    """Компания"""
    __tablename__ = "companies"

    id = Column(String, primary_key=True)  # SYNTHETIC_U
    client_type = Column(String, index=True)  # CL_TYPE
    org_type = Column(String)  # ORG_TYPE
    okved_code = Column(String, index=True)
    okved_name = Column(String)
    revenue = Column(Float, index=True)
    region = Column(String, index=True)
    city = Column(String)
    group_id = Column(String, index=True)

    # всё остальное в JSON (для контекста ллм)
    profile_json = Column(JSON, nullable=False)


class Person(Base):
    """Физлицо"""
    __tablename__ = "persons"

    id = Column(String, primary_key=True, default=_uuid)
    synthetic_f = Column(String, nullable=False, index=True)  # SYNTHETIC_F
    synthetic_u = Column(String, nullable=False, index=True)  # SYNTHETIC_U
    city_name = Column(String, nullable=True)  # CITY_NAME
    rc_name = Column(String, nullable=True)   # RC_NAME


class Payment(Base):
    """Платёж"""
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=_uuid)
    payer_id = Column(String, nullable=False, index=True)  # PAYER
    beneficiary_id = Column(String, nullable=False, index=True)  # BENEFICIARY
    pay_amt = Column(Float, nullable=False)  # PAY_AMT
    pay_cnt = Column(Float, nullable=False)  # PAY_CNT


class CompanyLink(Base):
    """Связь между компаниями"""
    __tablename__ = "company_links"

    id = Column(String, primary_key=True)
    src_id = Column(String, index=True)  # SYNTHETIC_U
    dst_id = Column(String, index=True)  # SYNTHETIC_U
    link_type = Column(String, index=True)  # тип связи (group, person, payment)
    weight = Column(Float, default=1.0)  # сила связи (может потом уберем)
    meta = Column(JSON, default=dict)  #


class News(Base):
    """Сырая новость"""
    __tablename__ = "news"

    id = Column(String, primary_key=True, default=_uuid)
    source = Column(String, nullable=False, index=True)
    source_authority = Column(Float, nullable=False, default=0.5)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    url = Column(String, nullable=False, unique=True)
    categories = Column(JSON, nullable=False, default=list)
    published_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    raw_hash = Column(String, nullable=False, index=True)


class Event(Base):
    """Обогащённая новость"""
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=_uuid)
    news_id = Column(
        String,
        ForeignKey("news.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    event_type = Column(String, nullable=False, index=True)
    entities = Column(JSON, nullable=False, default=list)
    sentiment = Column(String, nullable=False, default="neutral")  # направленность (negative, neutral, positive)
    confidence = Column(Float, nullable=False, default=0.0)  # от 0 до 1
    input_quality = Column(String, nullable=False, default="full")  # full.short | title_only
    reasoning = Column(Text, nullable=False, default="")

    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


