"""Maritime intelligence — AIS vessel tracking and port congestion.

Primary: VesselAPI (free tier, 695K vessels) — set VESSEL_API_KEY in .env
         Sign up at https://vesselapi.com — no credit card required

Without a key this module returns demo/empty data and shows a setup message.

Port congestion index = vessels_at_anchor / normal_baseline
  > 1.4 → congested (HIGH risk signal)
  > 1.2 → elevated (MEDIUM)
  ≤ 1.2 → normal
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

VESSEL_API_KEY = os.getenv("VESSEL_API_KEY", "")
VESSEL_BASE = "https://api.vesselapi.com/v1"

# Top 20 global ports critical to supply chains with their coordinates
STRATEGIC_PORTS: list[dict] = [
    {"name": "Port of Shanghai",        "country": "CN", "lat": 31.36, "lng": 121.62, "industry_relevance": ["electronics", "automotive", "textile"]},
    {"name": "Port of Singapore",       "country": "SG", "lat": 1.26,  "lng": 103.82, "industry_relevance": ["all"]},
    {"name": "Port of Rotterdam",       "country": "NL", "lat": 51.95, "lng": 4.13,   "industry_relevance": ["all"]},
    {"name": "Port of Los Angeles",     "country": "US", "lat": 33.74, "lng": -118.27,"industry_relevance": ["all"]},
    {"name": "Port of Shenzhen",        "country": "CN", "lat": 22.49, "lng": 113.97, "industry_relevance": ["electronics", "automotive"]},
    {"name": "Port of Busan",           "country": "KR", "lat": 35.10, "lng": 129.04, "industry_relevance": ["electronics", "automotive"]},
    {"name": "Port of Kaohsiung",       "country": "TW", "lat": 22.62, "lng": 120.28, "industry_relevance": ["electronics"]},
    {"name": "Port of Chittagong",      "country": "BD", "lat": 22.33, "lng": 91.78,  "industry_relevance": ["textile", "food_agriculture"]},
    {"name": "Port of Mumbai",          "country": "IN", "lat": 18.95, "lng": 72.84,  "industry_relevance": ["pharmaceutical", "textile"]},
    {"name": "Port of Hamburg",         "country": "DE", "lat": 53.55, "lng": 9.99,   "industry_relevance": ["automotive", "aerospace"]},
    {"name": "Port of Jebel Ali",       "country": "AE", "lat": 24.98, "lng": 55.06,  "industry_relevance": ["oil_energy", "all"]},
    {"name": "Port of Houston",         "country": "US", "lat": 29.73, "lng": -95.27, "industry_relevance": ["oil_energy", "aerospace"]},
    {"name": "Strait of Hormuz",        "country": "AE", "lat": 26.56, "lng": 56.25,  "industry_relevance": ["oil_energy"]},
    {"name": "Suez Canal",              "country": "EG", "lat": 30.00, "lng": 32.55,  "industry_relevance": ["all"]},
    {"name": "Red Sea (Bab-el-Mandeb)", "country": "YE", "lat": 12.58, "lng": 43.47,  "industry_relevance": ["all"]},
    {"name": "Port of Nagoya",          "country": "JP", "lat": 35.07, "lng": 136.88, "industry_relevance": ["automotive", "electronics"]},
    {"name": "Port of Valencia",        "country": "ES", "lat": 39.45, "lng": -0.32,  "industry_relevance": ["automotive", "food_agriculture"]},
    {"name": "Port of Ho Chi Minh",     "country": "VN", "lat": 10.77, "lng": 106.68, "industry_relevance": ["textile", "electronics"]},
    {"name": "Port of Klang",           "country": "MY", "lat": 3.00,  "lng": 101.39, "industry_relevance": ["electronics", "oil_energy"]},
    {"name": "Port of Felixstowe",      "country": "GB", "lat": 51.96, "lng": 1.35,   "industry_relevance": ["automotive", "all"]},
]


def _is_configured() -> bool:
    return bool(VESSEL_API_KEY)


def fetch_vessels_near_port(port: dict, radius_nm: float = 25) -> list[dict]:
    """Fetch vessels within radius_nm nautical miles of a port."""
    if not _is_configured():
        return []
    try:
        resp = httpx.get(
            f"{VESSEL_BASE}/vessel/list",
            params={
                "apiKey": VESSEL_API_KEY,
                "lat": port["lat"],
                "lng": port["lng"],
                "radius": radius_nm,
                "status": "1",  # at anchor / moored
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        logger.debug("[VesselAPI] port %s: %s", port["name"], exc)
        return []


def compute_congestion_index(vessels_at_anchor: int, port_name: str) -> float:
    """Simple congestion index vs per-port normal baselines."""
    baselines: dict[str, int] = {
        "Port of Shanghai": 45, "Port of Singapore": 30, "Port of Rotterdam": 20,
        "Port of Los Angeles": 35, "Port of Shenzhen": 25, "Port of Busan": 20,
        "Suez Canal": 15, "Strait of Hormuz": 25, "Red Sea (Bab-el-Mandeb)": 18,
    }
    baseline = baselines.get(port_name, 15)
    return round(vessels_at_anchor / max(baseline, 1), 2)


def fetch_port_congestion(industry: str = "all") -> list[dict[str, Any]]:
    """Return congestion data for ports relevant to the given industry.

    If VesselAPI key is not configured, returns demo data with is_demo=True.
    """
    relevant_ports = [
        p for p in STRATEGIC_PORTS
        if "all" in p["industry_relevance"] or industry in p["industry_relevance"]
    ]

    if not _is_configured():
        return _demo_port_data(relevant_ports)

    results = []
    for port in relevant_ports[:10]:  # cap at 10 to stay within free tier
        vessels = fetch_vessels_near_port(port)
        count = len(vessels)
        idx = compute_congestion_index(count, port["name"])
        level = "HIGH" if idx > 1.4 else ("MEDIUM" if idx > 1.2 else "NORMAL")
        results.append({
            "port_name": port["name"],
            "country": port["country"],
            "lat": port["lat"],
            "lng": port["lng"],
            "vessels_at_anchor": count,
            "congestion_index": idx,
            "level": level,
            "is_demo": False,
            "fetched_at": datetime.utcnow().isoformat(),
        })
    return results


def _demo_port_data(ports: list[dict]) -> list[dict]:
    """Return demo congestion data when no VesselAPI key is set."""
    import random
    random.seed(42)
    demo = []
    for port in ports:
        idx = round(random.uniform(0.7, 1.8), 2)
        level = "HIGH" if idx > 1.4 else ("MEDIUM" if idx > 1.2 else "NORMAL")
        demo.append({
            "port_name": port["name"],
            "country": port["country"],
            "lat": port["lat"],
            "lng": port["lng"],
            "vessels_at_anchor": int(idx * 15),
            "congestion_index": idx,
            "level": level,
            "is_demo": True,
            "fetched_at": datetime.utcnow().isoformat(),
        })
    return demo


def get_congestion_as_events(port_data: list[dict]) -> list[dict[str, Any]]:
    """Convert HIGH/MEDIUM congestion readings into event-shaped dicts for the pipeline."""
    events = []
    for p in port_data:
        if p.get("is_demo") or p["level"] == "NORMAL":
            continue
        headline = (
            f"Port congestion {p['level']} at {p['port_name']} ({p['country']}) — "
            f"congestion index {p['congestion_index']:.1f}x normal, "
            f"{p['vessels_at_anchor']} vessels at anchor"
        )
        events.append({
            "source": "vesselapi",
            "headline": headline,
            "url": f"https://vesselapi.com/port/{p['port_name'].replace(' ','_')}",
            "published_at": datetime.utcnow(),
        })
    return events
