"""Fetchers for GDELT, NewsAPI, and NOAA CAP alerts."""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPPLY_CHAIN_KEYWORDS = {
    "port", "shipping", "logistics", "tariff", "strike", "freight",
    "supply chain", "cargo", "container", "semiconductor", "factory",
    "manufacturing", "sanctions", "trade", "import", "export",
    "disruption", "shortage", "inventory", "warehouse", "rail",
    "pipeline", "refinery", "flood", "earthquake", "typhoon", "hurricane",
    "geopolitical", "conflict", "blockade", "congestion",
}


def _passes_keyword_filter(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in SUPPLY_CHAIN_KEYWORDS)


# ── GDELT ─────────────────────────────────────────────────────────────────────

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

def fetch_gdelt_events(max_records: int = 25) -> list[dict[str, Any]]:
    """Query GDELT for recent supply-chain-relevant articles."""
    for i, timespan in enumerate(("1h", "6h", "24h")):
        if i > 0:
            time.sleep(2)  # back off between retries to avoid rate limiting
        params = {
            "query": (
                "logistics OR shipping OR port OR tariff OR \"supply chain\" "
                "OR semiconductor OR freight OR strike OR factory"
            ),
            "mode": "artlist",
            "maxrecords": max_records,
            "format": "json",
            "timespan": timespan,
        }
        try:
            resp = httpx.get(GDELT_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            return [
                {
                    "source": "gdelt",
                    "headline": a.get("title", ""),
                    "url": a.get("url", ""),
                    "published_at": _parse_gdelt_date(a.get("seendate", "")),
                }
                for a in articles
                if a.get("url") and a.get("title") and _passes_keyword_filter(a.get("title", ""))
            ]
        except Exception as exc:
            print(f"[GDELT] fetch error (timespan={timespan}): {exc}")
    return []


def _parse_gdelt_date(ds: str) -> datetime | None:
    try:
        return datetime.strptime(ds, "%Y%m%dT%H%M%SZ")
    except Exception:
        return None


# ── NewsAPI ───────────────────────────────────────────────────────────────────

NEWSAPI_HEADLINES_BASE = "https://newsapi.org/v2/top-headlines"
NEWSAPI_EVERYTHING_BASE = "https://newsapi.org/v2/everything"

def fetch_newsapi_events() -> list[dict[str, Any]]:
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        print("[NewsAPI] NEWS_API_KEY not set — skipping")
        return []

    # Free tier restricts `everything` date filtering — use top-headlines + category,
    # then fall back to everything without date filter for broader supply chain coverage.
    results: list[dict[str, Any]] = []

    # Source 1: business top headlines (reliable on free tier)
    try:
        resp = httpx.get(
            NEWSAPI_HEADLINES_BASE,
            params={"category": "business", "language": "en", "pageSize": 30, "apiKey": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        for a in resp.json().get("articles", []):
            title = a.get("title", "")
            if a.get("url") and title and _passes_keyword_filter(title):
                results.append({
                    "source": "newsapi",
                    "headline": title,
                    "url": a["url"],
                    "published_at": _parse_iso(a.get("publishedAt")),
                })
    except Exception as exc:
        print(f"[NewsAPI/headlines] fetch error: {exc}")

    # Source 2: everything endpoint without date filter (free tier compatible)
    if not results:
        try:
            resp = httpx.get(
                NEWSAPI_EVERYTHING_BASE,
                params={
                    "q": "supply chain OR shipping OR port OR tariff OR semiconductor OR freight",
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 20,
                    "apiKey": api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            for a in resp.json().get("articles", []):
                title = a.get("title", "")
                if a.get("url") and title and _passes_keyword_filter(title):
                    results.append({
                        "source": "newsapi",
                        "headline": title,
                        "url": a["url"],
                        "published_at": _parse_iso(a.get("publishedAt")),
                    })
        except Exception as exc:
            print(f"[NewsAPI/everything] fetch error: {exc}")

    return results


def _parse_iso(ds: str | None) -> datetime | None:
    if not ds:
        return None
    try:
        return datetime.fromisoformat(ds.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


# ── NOAA CAP Alerts ───────────────────────────────────────────────────────────

NOAA_CAP_URL = "https://alerts.weather.gov/cap/us.php?x=1"

def fetch_noaa_alerts() -> list[dict[str, Any]]:
    """Parse NOAA CAP XML feed for severe weather events."""
    try:
        resp = httpx.get(NOAA_CAP_URL, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "cap": "urn:oasis:names:tc:emergency:cap:1.1",
        }
        events = []
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", default="", namespaces=ns)
            url = ""
            for link in entry.findall("atom:link", ns):
                url = link.get("href", "")
                break
            updated = _parse_iso(entry.findtext("atom:updated", namespaces=ns))

            # Only pass severe / extreme / hurricane / tornado events
            sev_terms = {"hurricane", "tornado", "flood", "typhoon", "extreme", "earthquake"}
            if not any(t in title.lower() for t in sev_terms):
                continue

            events.append({
                "source": "noaa",
                "headline": title,
                "url": url or f"https://alerts.weather.gov/#{hash(title)}",
                "published_at": updated,
            })
        return events
    except Exception as exc:
        print(f"[NOAA] fetch error: {exc}")
        return []


# ── Combined fetcher ──────────────────────────────────────────────────────────

def fetch_all_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    events.extend(fetch_gdelt_events())
    events.extend(fetch_newsapi_events())
    events.extend(fetch_noaa_alerts())
    return events
