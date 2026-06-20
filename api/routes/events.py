from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.crud import get_events_by_date_range, get_recent_events
from db.database import get_db

router = APIRouter(prefix="/events", tags=["events"])


class EventOut(BaseModel):
    id: str
    source: str
    headline: str
    url: str
    category: str
    affected_countries: list
    severity_hint: str
    published_at: datetime | None
    ingested_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[EventOut])
def list_events(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    return get_recent_events(db, limit=limit)


@router.get("/range", response_model=list[EventOut])
def events_by_range(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
):
    return get_events_by_date_range(db, start, end)
