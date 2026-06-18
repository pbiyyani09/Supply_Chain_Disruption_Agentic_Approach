"""Seed the Red Sea crisis scenario and demo suppliers into the database.

Run: python -m scripts.seed_demo
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.geo_matcher import get_lat_lng
from db.crud import create_event, event_exists, upsert_supplier
from db.database import SessionLocal, init_db

# ── Demo suppliers ─────────────────────────────────────────────────────────────
SEED_CSV = Path(__file__).parent.parent / "data" / "seed_suppliers.csv"

# ── Red Sea crisis events (Dec 2023 – Jan 2024) ─────────────────────────────────
RED_SEA_EVENTS = [
    {
        "source": "gdelt",
        "headline": "Houthi militants attack container ship in Red Sea shipping lane",
        "url": "https://example.com/red-sea-attack-dec18",
        "category": "geopolitical",
        "affected_countries": ["YE", "SA", "EG"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "Red Sea shipping lane attacked — major global freight transit route.",
        "published_at": datetime(2023, 12, 18, 9, 0),
    },
    {
        "source": "newsapi",
        "headline": "Maersk halts Red Sea transits indefinitely after attack on vessel",
        "url": "https://example.com/maersk-halts-dec19",
        "category": "logistics",
        "affected_countries": ["SA", "EG", "DJ"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "World's largest container shipper suspends Red Sea route.",
        "published_at": datetime(2023, 12, 19, 14, 30),
    },
    {
        "source": "newsapi",
        "headline": "Lloyd's of London raises war risk premiums for Red Sea passage",
        "url": "https://example.com/lloyds-war-risk-dec20",
        "category": "logistics",
        "affected_countries": ["YE", "SA", "EG", "OM"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "Insurance costs spike — shipping costs rising across Asia-Europe routes.",
        "published_at": datetime(2023, 12, 20, 11, 0),
    },
    {
        "source": "gdelt",
        "headline": "Port congestion at Singapore hits 3-week high as vessels reroute",
        "url": "https://example.com/singapore-congestion-dec22",
        "category": "logistics",
        "affected_countries": ["SG", "MY"],
        "severity_hint": "medium",
        "is_supply_chain_relevant": True,
        "brief_reason": "Rerouting via Cape of Good Hope causing Southeast Asia port backlog.",
        "published_at": datetime(2023, 12, 22, 7, 0),
    },
    {
        "source": "newsapi",
        "headline": "China exports face 14-day delay as Asia-Europe routes rerouted via Cape",
        "url": "https://example.com/china-delay-dec28",
        "category": "logistics",
        "affected_countries": ["CN", "TW", "KR"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "14-day shipping delays expected for all Asia-Europe cargo.",
        "published_at": datetime(2023, 12, 28, 10, 0),
    },
    {
        "source": "gdelt",
        "headline": "US, UK launch strikes on Houthi targets — Red Sea crisis escalates",
        "url": "https://example.com/us-uk-strikes-jan05",
        "category": "geopolitical",
        "affected_countries": ["YE", "SA", "EG", "OM", "DJ"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "Military escalation deepens uncertainty for Red Sea shipping.",
        "published_at": datetime(2024, 1, 5, 18, 0),
    },
]


def seed_suppliers(db) -> int:
    count = 0
    with open(SEED_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["country_code"].strip().upper()
            lat, lng = get_lat_lng(code)
            upsert_supplier(db, {
                "name": row["name"].strip(),
                "country_code": code,
                "product_category": row["product_category"].strip(),
                "tier": int(row["tier"]),
                "region": row.get("region", "").strip() or None,
                "lat": lat,
                "lng": lng,
            })
            count += 1
    return count


def seed_events(db) -> int:
    count = 0
    for ev in RED_SEA_EVENTS:
        if not event_exists(db, ev["url"]):
            create_event(db, ev)
            count += 1
            print(f"  [+] {ev['published_at'].date()} — {ev['headline'][:70]}")
        else:
            print(f"  [=] Already exists: {ev['headline'][:60]}")
    return count


def main() -> None:
    print("ChainWatch — Seeding demo data\n")
    init_db()
    db = SessionLocal()
    try:
        n_sup = seed_suppliers(db)
        print(f"Suppliers: {n_sup} upserted\n")

        print("Red Sea crisis events:")
        n_ev = seed_events(db)
        print(f"\nEvents: {n_ev} new events stored")

        print("\nDone! Now run the risk scorer to generate scores:")
        print("  python -c \"from agents.risk_scorer import run_risk_scorer; run_risk_scorer()\"")
    finally:
        db.close()


if __name__ == "__main__":
    main()
