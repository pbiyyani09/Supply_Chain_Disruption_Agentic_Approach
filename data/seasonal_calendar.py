"""Seasonal risk calendar — recurring annual disruption windows by industry and region.

These are known, predictable patterns that the forecasting agent uses to elevate
probability estimates for medium-term horizons (3m, 6m).

Each window:
  - months: list of month numbers (1=Jan … 12=Dec) when the risk is active
  - region_codes: ISO-2 country/region codes affected
  - risk_type: category matching Event.category schema
  - title: short human-readable label
  - description: detail shown in dashboard calendar
  - severity: "high" | "medium" | "low"
  - industries: which industry profiles are primarily affected
"""
from __future__ import annotations

from datetime import date

SEASONAL_WINDOWS: list[dict] = [
    # ── Weather / Natural ──────────────────────────────────────────────────────
    {
        "title": "Pacific Typhoon Season",
        "months": [6, 7, 8, 9, 10, 11],
        "region_codes": ["TW", "PH", "JP", "CN", "VN"],
        "risk_type": "weather",
        "severity": "high",
        "industries": ["electronics", "automotive", "pharmaceutical"],
        "description": "Peak typhoon activity in the Western Pacific. Taiwan semiconductor fabs, Philippine component factories and Vietnamese electronics plants face direct exposure.",
    },
    {
        "title": "South Asian Monsoon (Heavy Flooding)",
        "months": [6, 7, 8, 9],
        "region_codes": ["BD", "IN", "PK", "TH", "VN", "MY"],
        "risk_type": "weather",
        "severity": "high",
        "industries": ["textile", "food_agriculture", "pharmaceutical"],
        "description": "Bangladesh and Indian subcontinent monsoon brings severe flooding. Garment factories in Chittagong and Dhaka regularly suspend operations. Rice and wheat harvests at risk.",
    },
    {
        "title": "US Atlantic Hurricane Season",
        "months": [6, 7, 8, 9, 10, 11],
        "region_codes": ["US", "MX", "BS", "CU", "HT"],
        "risk_type": "weather",
        "severity": "high",
        "industries": ["oil_energy", "automotive", "food_agriculture"],
        "description": "Major hurricanes threaten US Gulf Coast oil platforms, Houston refineries, and automotive plants in the Southeast. Port of Houston and Port of New Orleans exposure.",
    },
    {
        "title": "South American Drought Season",
        "months": [11, 12, 1, 2, 3],
        "region_codes": ["BR", "AR", "UY", "PY"],
        "risk_type": "weather",
        "severity": "medium",
        "industries": ["food_agriculture"],
        "description": "La Niña-linked drought in Argentina and southern Brazil reduces soybean, corn, and wheat harvests. Brazil accounts for ~50% of global soy exports.",
    },
    {
        "title": "Australian Summer Bushfire Season",
        "months": [11, 12, 1, 2, 3],
        "region_codes": ["AU"],
        "risk_type": "weather",
        "severity": "medium",
        "industries": ["food_agriculture", "oil_energy", "aerospace"],
        "description": "Bushfires impact agricultural output and can disrupt mining operations critical for lithium and rare earth production.",
    },
    {
        "title": "Yangtze River Flood Season",
        "months": [6, 7, 8],
        "region_codes": ["CN"],
        "risk_type": "weather",
        "severity": "medium",
        "industries": ["electronics", "automotive", "pharmaceutical"],
        "description": "Annual flooding in the Yangtze basin disrupts road and rail logistics to manufacturing hubs in Wuhan, Nanjing, and Chongqing.",
    },

    # ── Operational / Cultural ─────────────────────────────────────────────────
    {
        "title": "Chinese New Year Factory Shutdown",
        "months": [1, 2],
        "region_codes": ["CN", "TW", "SG", "MY", "VN", "TH"],
        "risk_type": "logistics",
        "severity": "high",
        "industries": ["electronics", "automotive", "pharmaceutical", "textile"],
        "description": "2–4 week manufacturing halt across China and Chinese-run factories in SE Asia. Inventory buffers must be in place 6–8 weeks prior. Port of Shanghai throughput drops ~30%.",
    },
    {
        "title": "Diwali / Indian Holiday Production Dip",
        "months": [10, 11],
        "region_codes": ["IN"],
        "risk_type": "logistics",
        "severity": "low",
        "industries": ["pharmaceutical", "textile", "food_agriculture"],
        "description": "Reduced productivity in Indian pharmaceutical API plants and textile factories during Diwali week. Minor but predictable slowdown.",
    },
    {
        "title": "Year-End Western Manufacturing Slowdown",
        "months": [12],
        "region_codes": ["US", "DE", "FR", "UK", "IT", "ES", "CA"],
        "risk_type": "logistics",
        "severity": "low",
        "industries": ["automotive", "aerospace"],
        "description": "Western automotive and aerospace plants reduce shifts December 24–January 2. Tier-2 suppliers may close entirely, impacting just-in-time delivery windows.",
    },
    {
        "title": "Ramadan Production Slowdown — Gulf Region",
        "months": [3, 4],  # approximate — shifts yearly
        "region_codes": ["SA", "AE", "KW", "QA", "OM", "BH"],
        "risk_type": "logistics",
        "severity": "low",
        "industries": ["oil_energy"],
        "description": "Reduced working hours and lower productivity at Gulf oil infrastructure during Ramadan. Crude loading schedules may shift.",
    },

    # ── Geopolitical Seasonal ──────────────────────────────────────────────────
    {
        "title": "US–China Trade Tariff Review Season",
        "months": [3, 4, 9, 10],
        "region_codes": ["CN", "TW", "VN", "MX"],
        "risk_type": "geopolitical",
        "severity": "medium",
        "industries": ["electronics", "automotive", "textile"],
        "description": "USTR typically publishes tariff reviews and Section 301 updates in Q1 and Q3. Market uncertainty spikes as new tariff lists are rumored and published.",
    },
    {
        "title": "Taiwan Strait Military Tension Window",
        "months": [7, 8, 9],
        "region_codes": ["TW", "CN"],
        "risk_type": "geopolitical",
        "severity": "high",
        "industries": ["electronics", "automotive"],
        "description": "PLA military exercises around Taiwan historically cluster in summer months. Taiwan Strait navigation risk elevates for container shipping routes.",
    },
    {
        "title": "Ukraine Harvest / Grain Export Risk",
        "months": [6, 7, 8],
        "region_codes": ["UA", "RU"],
        "risk_type": "geopolitical",
        "severity": "high",
        "industries": ["food_agriculture"],
        "description": "Ukrainian wheat and sunflower harvest season. Ongoing conflict creates uncertainty in Black Sea grain corridor. Export volumes and pricing volatile.",
    },
    {
        "title": "Indian Election Campaign Season",
        "months": [3, 4, 5],
        "region_codes": ["IN"],
        "risk_type": "geopolitical",
        "severity": "medium",
        "industries": ["pharmaceutical", "textile", "food_agriculture"],
        "description": "General elections bring policy uncertainty, infrastructure delays, and labor unrest in India. Pharmaceutical API export policies may be reviewed.",
    },

    # ── Logistics ─────────────────────────────────────────────────────────────
    {
        "title": "Pre-Holiday US Retail Import Surge",
        "months": [8, 9, 10],
        "region_codes": ["CN", "VN", "BD", "IN"],
        "risk_type": "logistics",
        "severity": "medium",
        "industries": ["textile", "electronics"],
        "description": "Retailers front-load imports ahead of US Q4 holiday season. Container rates surge 30–60%, port congestion spikes at LA/Long Beach and East Coast ports.",
    },
    {
        "title": "Red Sea / Houthi Disruption Risk",
        "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "region_codes": ["YE", "EG", "SA", "ER"],
        "risk_type": "geopolitical",
        "severity": "high",
        "industries": ["all"],
        "description": "Ongoing Houthi attacks on commercial shipping in the Red Sea force vessels around Africa (+12–15 days transit). Major impact on Europe–Asia trade lanes.",
    },
]


def get_active_windows(month: int | None = None, industry: str = "all") -> list[dict]:
    """Return seasonal windows active in a given month for a given industry.

    month: 1–12 (defaults to current month if None)
    industry: industry key or "all"
    """
    if month is None:
        month = date.today().month

    return [
        w for w in SEASONAL_WINDOWS
        if month in w["months"]
        and (industry == "all" or "all" in w["industries"] or industry in w["industries"])
    ]


def get_upcoming_windows(industry: str = "all", look_ahead_months: int = 6) -> list[dict]:
    """Return windows that will be active within the next N months, with 'starts_in_days' added."""
    today = date.today()
    current_month = today.month
    results = []
    seen: set[str] = set()

    for offset in range(look_ahead_months + 1):
        m = ((current_month - 1 + offset) % 12) + 1
        for w in get_active_windows(m, industry):
            key = w["title"]
            if key in seen:
                continue
            seen.add(key)

            # Find the next start of this window
            next_start = _next_occurrence(w["months"], today)
            next_end = _window_end(w["months"], next_start)

            results.append({
                **w,
                "next_start": next_start.isoformat(),
                "next_end": next_end.isoformat(),
                "starts_in_days": (next_start - today).days,
            })

    return sorted(results, key=lambda x: x["starts_in_days"])


def _next_occurrence(months: list[int], today: date) -> date:
    for offset in range(13):
        m = ((today.month - 1 + offset) % 12) + 1
        year = today.year + (today.month - 1 + offset) // 12
        if m in months:
            return date(year, m, 1)
    return today


def _window_end(months: list[int], start: date) -> date:
    """Find the last month in the contiguous window that includes start."""
    m = start.month
    year = start.year
    # Walk forward until month is no longer in the window
    while True:
        next_m = (m % 12) + 1
        next_y = year + (1 if m == 12 else 0)
        if next_m not in months:
            break
        m, year = next_m, next_y
    # Return last day of last month
    import calendar
    last_day = calendar.monthrange(year, m)[1]
    return date(year, m, last_day)


def get_risk_context_for_country(country_code: str, industry: str) -> str:
    """Generate a text summary of active and upcoming seasonal risks for a supplier country."""
    today = date.today()
    active = [w for w in SEASONAL_WINDOWS if country_code in w["region_codes"] and today.month in w["months"]
              and (industry == "all" or "all" in w["industries"] or industry in w["industries"])]
    upcoming = [w for w in SEASONAL_WINDOWS if country_code in w["region_codes"]
                and any(((today.month - 1 + i) % 12) + 1 in w["months"] for i in range(1, 4))
                and (industry == "all" or "all" in w["industries"] or industry in w["industries"])]
    upcoming = [w for w in upcoming if w not in active]

    parts = []
    if active:
        parts.append("ACTIVE SEASONAL RISKS: " + "; ".join(w["title"] for w in active))
    if upcoming:
        parts.append("UPCOMING IN 3 MONTHS: " + "; ".join(w["title"] for w in upcoming))
    return "\n".join(parts) if parts else "No significant seasonal risks in the current or next 3-month window."
