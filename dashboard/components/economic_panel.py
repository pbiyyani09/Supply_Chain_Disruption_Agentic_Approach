"""Economic Signal Panel — live macro indicators that serve as leading risk signals."""
from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

_TREND_ICON = {"rising": "📈", "falling": "📉", "stable": "➡️"}
_TREND_COLOR = {"rising": "red", "falling": "green", "stable": "gray"}

_RISK_NOTE = {
    "WTI_CRUDE":       "Rising oil prices raise freight and petrochemical input costs across all industries.",
    "NATURAL_GAS":     "Higher gas prices increase energy costs for manufacturing and cold-chain logistics.",
    "COPPER":          "Copper is a bellwether for electronics and automotive demand; rising prices signal input cost pressure.",
    "ALUMINUM":        "Aluminum price spikes impact aerospace, automotive, and packaging costs.",
    "IRON_ORE":        "Iron ore drives steel prices, directly affecting automotive and construction supply chains.",
    "FOOD_INDEX":      "Rising food commodity index pressures food manufacturers and packaging costs.",
    "WHEAT":           "Wheat price spikes signal grain supply disruptions, often linked to Black Sea conflict or drought.",
    "SOYBEAN":         "Soybean prices affect food processing, animal feed, and biodiesel supply chains.",
    "COTTON":          "Cotton price movements directly drive apparel and textile input costs.",
    "COMMODITY_INDEX": "Broad commodity index captures overall inflationary pressure on global supply chains.",
    "FREIGHT_PPI":     "Freight PPI measures trucking cost trends — a direct logistics cost signal.",
}


@st.cache_data(ttl=300)
def _get_signals() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/economic-signals/", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def render_economic_panel(industry: str = "all") -> None:
    st.subheader("Economic Signal Dashboard")
    st.caption("Leading macro indicators that predict supply chain disruptions 30–90 days ahead.")

    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        if st.button("Refresh Signals", use_container_width=True):
            try:
                requests.post(f"{API_BASE}/scan/economics", params={"industry": industry}, timeout=60)
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"Refresh failed: {exc}")
    with col_info:
        st.caption(
            "**FRED API:** Add `FRED_API_KEY` in `.env` for real-time prices (free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)). "
            "Without it, World Bank monthly data is used as fallback."
        )

    signals = _get_signals()

    if not signals:
        st.info(
            "No economic signals yet. Click **Refresh Signals** or run a scan. "
            "Set `FRED_API_KEY` in `.env` for real-time commodity prices."
        )
        return

    # Sort: most volatile (largest |change_pct|) first
    signals.sort(key=lambda s: abs(s.get("change_pct_30d") or 0), reverse=True)

    # ── Summary row ────────────────────────────────────────────────────────────
    rising = sum(1 for s in signals if s.get("trend") == "rising")
    falling = sum(1 for s in signals if s.get("trend") == "falling")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Indicators Tracked", len(signals))
    m2.metric("Rising", rising, delta=f"+{rising}" if rising else None,
              delta_color="inverse" if rising else "off")
    m3.metric("Falling", falling, delta=f"-{falling}" if falling else None,
              delta_color="normal" if falling else "off")
    m4.metric("Stable", len(signals) - rising - falling)

    st.divider()

    # ── Individual indicator cards in a grid ───────────────────────────────────
    cols_per_row = 3
    for row_start in range(0, len(signals), cols_per_row):
        cols = st.columns(cols_per_row)
        for ci, signal in enumerate(signals[row_start : row_start + cols_per_row]):
            with cols[ci]:
                trend = signal.get("trend", "stable")
                icon = _TREND_ICON.get(trend, "➡️")
                chg = signal.get("change_pct_30d")
                chg_str = f"{chg:+.1f}% (30d)" if chg is not None else "n/a"
                val = signal.get("value", 0)

                st.metric(
                    label=f"{icon} {signal.get('label', signal['indicator'])}",
                    value=f"{val:,.2f}",
                    delta=chg_str,
                    delta_color="inverse" if trend == "rising" else ("normal" if trend == "falling" else "off"),
                    help=_RISK_NOTE.get(signal["indicator"], ""),
                )
                st.caption(f"Source: {signal.get('source', '?').upper()} · {signal.get('date', '')}")

    st.divider()

    # ── Risk interpretation ────────────────────────────────────────────────────
    st.subheader("Signal Interpretation")
    risk_signals = [s for s in signals if s.get("trend") in ("rising", "falling")]
    if not risk_signals:
        st.success("All tracked indicators are stable — no commodity-driven risk signals at this time.")
    else:
        for s in risk_signals[:6]:
            trend = s.get("trend", "stable")
            icon = _TREND_ICON[trend]
            note = _RISK_NOTE.get(s["indicator"], "Monitor this indicator for supply chain cost impacts.")
            st.markdown(f"{icon} **{s['label']}** ({s['change_pct_30d']:+.1f}% over 30 days): {note}")
