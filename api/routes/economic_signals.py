"""Economic signals API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data.economic_signals import get_signal_label, get_signal_trend
from db.crud import get_latest_signals, get_signal_history
from db.database import get_db

router = APIRouter(prefix="/economic-signals", tags=["economic-signals"])


def _serialize(signal) -> dict:
    return {
        "id": signal.id,
        "indicator": signal.indicator,
        "label": get_signal_label(signal.indicator),
        "value": signal.value,
        "change_pct_30d": signal.change_pct_30d,
        "trend": get_signal_trend(signal.change_pct_30d),
        "date": str(signal.date)[:10],
        "source": signal.source,
        "fetched_at": str(signal.fetched_at)[:19],
    }


@router.get("/")
def list_latest_signals(db: Session = Depends(get_db)):
    """Return the most recent value for each tracked indicator."""
    signals = get_latest_signals(db)
    return [_serialize(s) for s in signals]


@router.get("/{indicator}/history")
def signal_history(indicator: str, limit: int = 12, db: Session = Depends(get_db)):
    """Return historical values for a specific indicator."""
    rows = get_signal_history(db, indicator, limit=limit)
    return [_serialize(r) for r in rows]
