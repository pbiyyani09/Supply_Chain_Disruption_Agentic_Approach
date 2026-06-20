"""Fetch macro-economic indicators that serve as leading signals for supply chain risk.

Primary source: FRED API (free key from fred.stlouisfed.org → add FRED_API_KEY to .env)
Fallback:       World Bank Open Data API (no key required, monthly data)

Indicators tracked by industry:
  ALL       → WTI Crude Oil, Global Commodity Index
  electronics   → Copper, Semiconductor export indices
  automotive    → Steel/Iron Ore, Lithium (via copper proxy)
  pharmaceutical → API chemical index proxied via PPI
  food_agriculture → Food Price Index, Wheat, Soybean
  oil_energy    → WTI, Natural Gas, Brent
  textile       → Cotton
  aerospace     → Titanium proxied via Aluminum
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# FRED series IDs (all freely available)
FRED_SERIES: dict[str, dict] = {
    "WTI_CRUDE":       {"series_id": "DCOILWTICO",      "label": "WTI Crude Oil ($/bbl)",    "industries": ["all"]},
    "NATURAL_GAS":     {"series_id": "DHHNGSP",         "label": "Natural Gas ($/MMBtu)",    "industries": ["oil_energy", "food_agriculture"]},
    "COPPER":          {"series_id": "PCOPPUSDM",        "label": "Copper Price ($/MT)",      "industries": ["electronics", "automotive", "aerospace"]},
    "ALUMINUM":        {"series_id": "PALUMUSDM",        "label": "Aluminum Price ($/MT)",    "industries": ["aerospace", "automotive"]},
    "IRON_ORE":        {"series_id": "PIORECRUSDM",      "label": "Iron Ore Price ($/DMT)",   "industries": ["automotive", "aerospace"]},
    "FOOD_INDEX":      {"series_id": "PFOODINDEXM",      "label": "Food Commodity Index",     "industries": ["food_agriculture", "pharmaceutical"]},
    "WHEAT":           {"series_id": "PWHEAMTUSDM",      "label": "Wheat Price ($/MT)",       "industries": ["food_agriculture"]},
    "SOYBEAN":         {"series_id": "PSOYBUSDM",        "label": "Soybean Price ($/MT)",     "industries": ["food_agriculture", "textile"]},
    "COTTON":          {"series_id": "PCOTTINDUSDM",     "label": "Cotton Price (cents/lb)",  "industries": ["textile"]},
    "COMMODITY_INDEX": {"series_id": "PALLFNFINDEXM",    "label": "All Commodities Index",    "industries": ["all"]},
    "FREIGHT_PPI":     {"series_id": "PCU484121484121",  "label": "General Freight Trucking PPI", "industries": ["all"]},
}

# Yahoo Finance symbols for no-key fallback (unofficial API, real-time)
YAHOO_SYMBOLS: dict[str, dict] = {
    "WTI_CRUDE":       {"symbol": "CL=F",   "label": "WTI Crude Oil ($/bbl)"},
    "NATURAL_GAS":     {"symbol": "NG=F",   "label": "Natural Gas ($/MMBtu)"},
    "COPPER":          {"symbol": "HG=F",   "label": "Copper ($/lb)"},
    "ALUMINUM":        {"symbol": "ALI=F",  "label": "Aluminum ($/MT)"},
    "IRON_ORE":        {"symbol": "TIO=F",  "label": "Iron Ore ($/MT)"},
    "WHEAT":           {"symbol": "ZW=F",   "label": "Wheat (cents/bushel)"},
    "SOYBEAN":         {"symbol": "ZS=F",   "label": "Soybean (cents/bushel)"},
    "COTTON":          {"symbol": "CT=F",   "label": "Cotton (cents/lb)"},
    "COMMODITY_INDEX": {"symbol": "DJP",    "label": "Commodity Index (iPath ETF)"},
}


def _fred_fetch(series_id: str, lookback_days: int = 90) -> list[dict]:
    """Fetch recent observations from FRED. Returns [{date, value}]."""
    if not FRED_API_KEY:
        return []
    start = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    try:
        resp = httpx.get(
            FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "observation_start": start,
                "sort_order": "desc",
                "limit": 12,
            },
            timeout=15,
        )
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        return [
            {"date": o["date"], "value": float(o["value"])}
            for o in obs
            if o.get("value") not in (".", "")
        ]
    except Exception as exc:
        logger.warning("[FRED] fetch failed for %s: %s", series_id, exc)
        return []


def _yahoo_fetch(symbol: str, lookback_days: int = 90) -> list[dict]:
    """Fetch real-time price data from Yahoo Finance (no API key required)."""
    try:
        resp = httpx.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1d", "range": "3mo"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json().get("chart", {}).get("result", [])
        if not result:
            return []

        timestamps = result[0].get("timestamp", [])
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])

        obs = []
        for ts, val in zip(timestamps, closes, strict=False):
            if val is not None:
                dt = datetime.fromtimestamp(ts)
                obs.append({"date": dt.strftime("%Y-%m-%d"), "value": float(val)})

        return sorted(obs, key=lambda x: x["date"], reverse=True)
    except Exception as exc:
        logger.warning("[Yahoo] fetch failed for %s: %s", symbol, exc)
        return []


def _compute_change_pct(observations: list[dict]) -> float | None:
    """Return % change from oldest to newest observation."""
    if len(observations) < 2:
        return None
    newest = observations[0]["value"]
    oldest = observations[-1]["value"]
    if oldest == 0:
        return None
    return round((newest - oldest) / oldest * 100, 2)


def fetch_economic_signals(industry: str = "all") -> list[dict]:
    """Fetch all relevant indicators for the given industry.

    Returns a list of dicts ready for upsert_economic_signal():
      {indicator, value, change_pct_30d, date, source}
    """
    results: list[dict] = []

    for key, meta in FRED_SERIES.items():
        if "all" not in meta["industries"] and industry not in meta["industries"]:
            continue

        series_id = meta["series_id"]

        if FRED_API_KEY:
            obs = _fred_fetch(series_id)
            source = "fred"
        else:
            # Fall back to Yahoo Finance (no key, real-time)
            yh_meta = YAHOO_SYMBOLS.get(key)
            obs = _yahoo_fetch(yh_meta["symbol"]) if yh_meta else []
            source = "yahoo"

        if not obs:
            continue

        change = _compute_change_pct(obs)
        latest = obs[0]
        try:
            date = datetime.strptime(latest["date"][:10], "%Y-%m-%d")
        except Exception:
            continue

        results.append({
            "indicator": key,
            "value": latest["value"],
            "change_pct_30d": change,
            "date": date,
            "source": source,
        })
        logger.info("[EconSignals] %s = %.2f (Δ30d: %s%%)", key, latest["value"],
                    f"{change:+.1f}" if change is not None else "n/a")

    return results


def get_signal_label(indicator: str) -> str:
    meta = FRED_SERIES.get(indicator)
    return meta["label"] if meta else indicator


def get_signal_trend(change_pct: float | None) -> str:
    """Return 'rising' | 'falling' | 'stable' from a % change."""
    if change_pct is None:
        return "stable"
    if change_pct > 5:
        return "rising"
    if change_pct < -5:
        return "falling"
    return "stable"
