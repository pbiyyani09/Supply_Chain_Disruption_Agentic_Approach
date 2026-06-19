"""Open-Meteo weather alerts for supplier locations.

Uses the Open-Meteo free API (no key required):
  https://api.open-meteo.com

Called with a list of suppliers (each with lat/lng/country_code).
Returns a list of raw event dicts (same shape as GDELT/NewsAPI events)
for any supplier location experiencing severe conditions.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Thresholds that trigger a weather risk event
_WIND_KMH_THRESHOLD = 65       # >65 km/h = potential storm
_PRECIP_MM_THRESHOLD = 50      # >50 mm/day = flood risk
_TEMP_MAX_THRESHOLD = 42       # >42°C = extreme heat (factory cooling risk)
_TEMP_MIN_THRESHOLD = -15      # <-15°C = extreme cold (logistics breakdown)

WMO_SEVERE_CODES = {
    # WMO weather interpretation codes that we treat as severe
    55, 57, 67, 75, 77, 82, 85, 86,   # heavy drizzle, ice pellets, heavy snow
    95, 96, 99,                          # thunderstorm, thunderstorm with hail
}


def fetch_weather_for_suppliers(suppliers: list[dict]) -> list[dict[str, Any]]:
    """Return weather-based risk events for any supplier with extreme conditions."""
    events: list[dict[str, Any]] = []

    for supplier in suppliers:
        lat = supplier.get("lat")
        lng = supplier.get("lng")
        if lat is None or lng is None:
            continue

        name = supplier.get("name", "Unknown")
        country = supplier.get("country_code", "??")

        try:
            resp = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
                    "forecast_days": 7,
                    "timezone": "UTC",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("[Weather] skip %s: %s", name, exc)
            continue

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        wmo_codes = daily.get("weathercode", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        wind = daily.get("windspeed_10m_max", [])

        for i, date_str in enumerate(dates[:3]):  # look at next 3 days
            alerts_found: list[str] = []

            wmo = wmo_codes[i] if i < len(wmo_codes) else 0
            if wmo in WMO_SEVERE_CODES:
                alerts_found.append(f"severe weather (WMO code {wmo})")

            prec = precip[i] if i < len(precip) else 0
            if prec and prec > _PRECIP_MM_THRESHOLD:
                alerts_found.append(f"extreme precipitation {prec:.0f} mm/day (flood risk)")

            w = wind[i] if i < len(wind) else 0
            if w and w > _WIND_KMH_THRESHOLD:
                alerts_found.append(f"high wind {w:.0f} km/h")

            tx = temp_max[i] if i < len(temp_max) else None
            tn = temp_min[i] if i < len(temp_min) else None
            if tx and tx > _TEMP_MAX_THRESHOLD:
                alerts_found.append(f"extreme heat {tx:.0f}°C")
            if tn and tn < _TEMP_MIN_THRESHOLD:
                alerts_found.append(f"extreme cold {tn:.0f}°C")

            if not alerts_found:
                continue

            description = " and ".join(alerts_found)
            headline = f"Weather alert at {name} ({country}): {description} forecast {date_str}"
            url = f"https://open-meteo.com/#{name.replace(' ','_')}_{date_str}"

            try:
                pub_dt = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                pub_dt = datetime.utcnow()

            events.append({
                "source": "openmeteo",
                "headline": headline,
                "url": url,
                "published_at": pub_dt,
            })
            logger.info("[Weather] Alert: %s", headline)

    return events
