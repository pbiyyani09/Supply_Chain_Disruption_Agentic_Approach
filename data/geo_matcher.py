from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from db.crud import get_suppliers_by_countries
from db.models import Supplier

_CENTROIDS_PATH = Path(__file__).parent / "country_centroids.json"
_centroids: dict[str, dict] = json.loads(_CENTROIDS_PATH.read_text())

# Country code aliases so Claude doesn't have to be perfect
_ALIASES: dict[str, str] = {
    "HK": "CN",  # Hong Kong → China
    "MO": "CN",  # Macao → China
    "TW": "TW",
    "UK": "GB",
    "ENG": "GB",
}


def resolve_country_code(code: str) -> str:
    return _ALIASES.get(code.upper(), code.upper())


def get_lat_lng(country_code: str) -> tuple[float | None, float | None]:
    code = resolve_country_code(country_code)
    centroid = _centroids.get(code)
    if centroid:
        return centroid["lat"], centroid["lng"]
    return None, None


def match_suppliers_to_event(
    db: Session, affected_countries: list[str]
) -> list[Supplier]:
    resolved = [resolve_country_code(c) for c in affected_countries]
    return get_suppliers_by_countries(db, resolved)
