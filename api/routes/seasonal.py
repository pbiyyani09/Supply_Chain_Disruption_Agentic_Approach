"""Seasonal risk calendar API routes."""
from __future__ import annotations

from fastapi import APIRouter, Query

from data.seasonal_calendar import get_active_windows, get_upcoming_windows, SEASONAL_WINDOWS

router = APIRouter(prefix="/seasonal-risks", tags=["seasonal-risks"])


@router.get("/")
def all_windows():
    """Return the complete seasonal risk calendar."""
    return SEASONAL_WINDOWS


@router.get("/active")
def active_windows(month: int = Query(None), industry: str = Query("all")):
    """Return windows active in a given month (defaults to current month)."""
    return get_active_windows(month=month, industry=industry)


@router.get("/upcoming")
def upcoming_windows(industry: str = Query("all"), look_ahead_months: int = Query(6)):
    """Return windows starting within the next N months."""
    return get_upcoming_windows(industry=industry, look_ahead_months=look_ahead_months)
