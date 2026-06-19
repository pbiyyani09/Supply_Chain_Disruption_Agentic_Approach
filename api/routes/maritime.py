"""Maritime / port congestion API routes."""
from __future__ import annotations

from fastapi import APIRouter, Query

from data.maritime import fetch_port_congestion, STRATEGIC_PORTS

router = APIRouter(prefix="/maritime", tags=["maritime"])


@router.get("/ports")
def list_strategic_ports():
    """Return the list of monitored strategic ports."""
    return STRATEGIC_PORTS


@router.get("/congestion")
def port_congestion(industry: str = Query("all")):
    """Return current vessel congestion index per strategic port.

    Returns demo data if VESSEL_API_KEY is not configured.
    """
    return fetch_port_congestion(industry=industry)
