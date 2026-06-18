import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    country_code = Column(String(2), nullable=False, index=True)
    region = Column(String, nullable=True)
    product_category = Column(String, nullable=False)
    tier = Column(Integer, nullable=False, default=1)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    risk_scores = relationship("RiskScore", back_populates="supplier")


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=_uuid)
    source = Column(String, nullable=False)  # gdelt | newsapi | noaa
    headline = Column(Text, nullable=False)
    url = Column(String, nullable=False, unique=True)  # dedup key
    category = Column(String, nullable=False)  # weather|geopolitical|logistics|labor|cyber
    affected_countries = Column(JSON, nullable=False, default=list)
    severity_hint = Column(String, nullable=False, default="medium")  # low|medium|high
    is_supply_chain_relevant = Column(Boolean, default=True)
    brief_reason = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    risk_scores = relationship("RiskScore", back_populates="event")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        UniqueConstraint("event_id", "supplier_id", name="uq_event_supplier"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False, index=True)
    score = Column(Integer, nullable=False)  # 1-10
    impact_window = Column(String, nullable=False)  # '24h', '72h', '1-2 weeks', etc.
    affected_tiers = Column(JSON, default=list)
    reasoning = Column(Text, nullable=False)
    scored_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="risk_scores")
    supplier = relationship("Supplier", back_populates="risk_scores")
    alert = relationship("Alert", back_populates="risk_score", uselist=False)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=_uuid)
    risk_score_id = Column(String, ForeignKey("risk_scores.id"), nullable=False, index=True)
    level = Column(String, nullable=False)  # HIGH | MEDIUM | LOW
    brief = Column(Text, nullable=True)
    alternatives = Column(JSON, default=list)
    dispatched_via = Column(JSON, default=list)  # ['slack', 'email']
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    risk_score = relationship("RiskScore", back_populates="alert")
