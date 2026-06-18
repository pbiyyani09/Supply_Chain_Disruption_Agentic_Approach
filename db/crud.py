from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from db.models import Alert, Event, RiskScore, Supplier


# ── Suppliers ─────────────────────────────────────────────────────────────────

def upsert_supplier(db: Session, data: dict) -> Supplier:
    existing = db.query(Supplier).filter(Supplier.name == data["name"]).first()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing
    supplier = Supplier(**data)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def get_suppliers(db: Session) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.name).all()


def get_suppliers_by_countries(db: Session, country_codes: list[str]) -> list[Supplier]:
    return db.query(Supplier).filter(Supplier.country_code.in_(country_codes)).all()


# ── Events ────────────────────────────────────────────────────────────────────

def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def event_exists(db: Session, url: str) -> bool:
    return db.query(Event).filter(Event.url == url).first() is not None


def create_event(db: Session, data: dict) -> Event:
    event = Event(**data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_recent_events(db: Session, limit: int = 100) -> list[Event]:
    return (
        db.query(Event)
        .filter(Event.is_supply_chain_relevant == True)
        .order_by(Event.ingested_at.desc())
        .limit(limit)
        .all()
    )


def get_events_by_date_range(db: Session, start: datetime, end: datetime) -> list[Event]:
    return (
        db.query(Event)
        .filter(Event.published_at >= start, Event.published_at <= end)
        .order_by(Event.published_at.asc())
        .all()
    )


# ── Risk Scores ───────────────────────────────────────────────────────────────

def risk_score_exists(db: Session, event_id: str, supplier_id: str) -> bool:
    return (
        db.query(RiskScore)
        .filter(RiskScore.event_id == event_id, RiskScore.supplier_id == supplier_id)
        .first()
    ) is not None


def create_risk_score(db: Session, data: dict) -> RiskScore:
    rs = RiskScore(**data)
    db.add(rs)
    db.commit()
    db.refresh(rs)
    return rs


def get_high_risk_scores(
    db: Session, threshold: int = 7, limit: int = 50
) -> list[RiskScore]:
    return (
        db.query(RiskScore)
        .filter(RiskScore.score >= threshold)
        .order_by(RiskScore.scored_at.desc())
        .limit(limit)
        .all()
    )


def get_risk_scores_for_supplier(
    db: Session, supplier_id: str, days: int = 7
) -> list[RiskScore]:
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(RiskScore)
        .filter(RiskScore.supplier_id == supplier_id, RiskScore.scored_at >= since)
        .order_by(RiskScore.scored_at.desc())
        .all()
    )


# ── Alerts ────────────────────────────────────────────────────────────────────

def alert_in_cooldown(
    db: Session, supplier_id: str, category: str, cooldown_hours: int = 24
) -> bool:
    since = datetime.utcnow() - timedelta(hours=cooldown_hours)
    return (
        db.query(Alert)
        .join(RiskScore)
        .join(Event)
        .filter(
            RiskScore.supplier_id == supplier_id,
            Event.category == category,
            Alert.created_at >= since,
        )
        .first()
    ) is not None


def create_alert(db: Session, data: dict) -> Alert:
    alert = Alert(**data)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_recent_alerts(db: Session, limit: int = 20) -> list[Alert]:
    return (
        db.query(Alert)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )


def mark_alert_read(db: Session, alert_id: str) -> Optional[Alert]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.is_read = True
        db.commit()
        db.refresh(alert)
    return alert


def get_unread_count(db: Session) -> int:
    return db.query(Alert).filter(Alert.is_read == False).count()
