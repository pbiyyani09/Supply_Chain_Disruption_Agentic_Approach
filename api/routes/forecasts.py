"""Forecast API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.crud import get_all_latest_forecasts, get_forecasts_for_supplier
from db.database import get_db

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


def _serialize(fc) -> dict:
    return {
        "id": fc.id,
        "supplier_id": fc.supplier_id,
        "supplier_name": fc.supplier.name if fc.supplier else "",
        "supplier_country": fc.supplier.country_code if fc.supplier else "",
        "industry": fc.industry,
        "horizon": fc.horizon,
        "disruption_probability": fc.disruption_probability,
        "disruption_pct": round(fc.disruption_probability * 100),
        "confidence": fc.confidence,
        "drivers": fc.drivers or [],
        "scenario": fc.scenario or "",
        "overall_trend": fc.overall_trend or "stable",
        "created_at": str(fc.created_at)[:19],
    }


@router.get("/")
def list_forecasts(db: Session = Depends(get_db)):
    """Return latest forecasts for all suppliers (all horizons)."""
    fcs = get_all_latest_forecasts(db)
    return [_serialize(fc) for fc in fcs]


@router.get("/supplier/{supplier_id}")
def forecasts_for_supplier(supplier_id: str, db: Session = Depends(get_db)):
    """Return all 6 horizon forecasts for a specific supplier."""
    fcs = get_forecasts_for_supplier(db, supplier_id)
    return [_serialize(fc) for fc in fcs]


@router.get("/summary")
def forecast_summary(db: Session = Depends(get_db)):
    """Return highest-risk horizon per supplier as a summary view."""
    fcs = get_all_latest_forecasts(db)
    by_supplier: dict[str, list] = {}
    for fc in fcs:
        by_supplier.setdefault(fc.supplier_id, []).append(fc)

    summaries = []
    for sid, rows in by_supplier.items():
        max_fc = max(rows, key=lambda r: r.disruption_probability)
        summaries.append({
            "supplier_id": sid,
            "supplier_name": max_fc.supplier.name if max_fc.supplier else "",
            "supplier_country": max_fc.supplier.country_code if max_fc.supplier else "",
            "peak_horizon": max_fc.horizon,
            "peak_probability": max_fc.disruption_probability,
            "peak_pct": round(max_fc.disruption_probability * 100),
            "overall_trend": max_fc.overall_trend or "stable",
            "horizon_count": len(rows),
        })
    return sorted(summaries, key=lambda s: s["peak_probability"], reverse=True)
