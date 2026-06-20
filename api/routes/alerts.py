from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.crud import get_recent_alerts, get_unread_count, mark_alert_read
from db.database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: str
    level: str
    brief: str | None
    alternatives: list
    dispatched_via: list
    is_read: bool
    created_at: datetime | None
    supplier_name: str | None = None
    supplier_country: str | None = None
    event_headline: str | None = None
    event_category: str | None = None
    score: int | None = None
    impact_window: str | None = None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db)):
    alerts = get_recent_alerts(db, limit=50)
    results = []
    for a in alerts:
        rs = a.risk_score
        results.append(
            AlertOut(
                id=a.id,
                level=a.level,
                brief=a.brief,
                alternatives=a.alternatives or [],
                dispatched_via=a.dispatched_via or [],
                is_read=a.is_read,
                created_at=a.created_at,
                supplier_name=rs.supplier.name if rs else None,
                supplier_country=rs.supplier.country_code if rs else None,
                event_headline=rs.event.headline if rs else None,
                event_category=rs.event.category if rs else None,
                score=rs.score if rs else None,
                impact_window=rs.impact_window if rs else None,
            )
        )
    return results


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db)):
    return {"count": get_unread_count(db)}


@router.post("/{alert_id}/read")
def mark_read(alert_id: str = Path(...), db: Session = Depends(get_db)):
    alert = mark_alert_read(db, alert_id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}
