"""Forecast Tab — multi-horizon disruption probability forecasts per supplier."""
from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

_HORIZON_LABELS = {
    "15d": "15 Days",
    "30d": "30 Days",
    "3m": "3 Months",
    "6m": "6 Months",
    "1y": "1 Year",
    "2y": "2 Years",
}

_CONFIDENCE_ICON = {"high": "🔴", "medium": "🟡", "low": "🔵"}
_TREND_ICON = {"escalating": "📈", "stable": "➡️", "improving": "📉"}

def _prob_color(p: float) -> str:
    if p >= 0.65:
        return "#dc3545"
    if p >= 0.4:
        return "#fd7e14"
    if p >= 0.2:
        return "#ffc107"
    return "#28a745"


@st.cache_data(ttl=120)
def _get_forecasts() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/forecasts/", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=120)
def _get_summary() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/forecasts/summary", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def _prob_bar(prob: float, width: int = 200) -> str:
    pct = int(prob * 100)
    color = _prob_color(prob)
    filled = int(pct * width / 100)
    return (
        f'<div style="display:inline-flex;align-items:center;gap:8px;">'
        f'<div style="width:{width}px;height:16px;background:#e9ecef;border-radius:8px;overflow:hidden;">'
        f'<div style="width:{filled}px;height:100%;background:{color};border-radius:8px;"></div>'
        f'</div>'
        f'<span style="color:{color};font-weight:bold;">{pct}%</span>'
        f'</div>'
    )


def render_forecast_tab(suppliers: list[dict], industry: str = "electronics") -> None:
    st.subheader("Disruption Probability Forecasts")
    st.caption(
        "AI-generated forward-looking risk forecasts per supplier. "
        "Powered by Gemini, combining live events, economic signals, and seasonal patterns."
    )

    col_run, col_note = st.columns([1, 3])
    with col_run:
        if st.button("Regenerate Forecasts", use_container_width=True):
            with st.spinner("Running Gemini forecasting across all suppliers..."):
                try:
                    r = requests.post(
                        f"{API_BASE}/scan/forecast",
                        params={"industry": industry},
                        timeout=300,
                    )
                    result = r.json()
                    st.success(f"Generated {result.get('forecasts_saved', 0)} forecast rows.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Forecast run failed: {exc}")
    with col_note:
        st.caption(
            "Short-term horizons (15d/30d) reflect current events. "
            "Long-term horizons incorporate seasonal patterns and structural trends. "
            "Confidence icon: 🔴 High · 🟡 Medium · 🔵 Low"
        )

    summary = _get_summary()
    all_forecasts = _get_forecasts()

    if not summary:
        st.info("No forecasts yet. Click **Regenerate Forecasts** or run a full scan from the sidebar.")
        return

    # ── Portfolio heatmap ──────────────────────────────────────────────────────
    st.subheader("Portfolio Forecast Heatmap")
    _render_heatmap(summary, all_forecasts)

    st.divider()

    # ── Supplier selector for detailed view ───────────────────────────────────
    st.subheader("Supplier Deep-Dive")
    supplier_names = [s["supplier_name"] for s in summary]
    selected_name = st.selectbox("Select a supplier", supplier_names)

    if selected_name:
        selected_summary = next((s for s in summary if s["supplier_name"] == selected_name), None)

        if selected_summary:
            trend_icon = _TREND_ICON.get(selected_summary.get("overall_trend", "stable"), "➡️")
            st.caption(
                f"Overall trend: {trend_icon} **{selected_summary.get('overall_trend', 'stable').title()}** · "
                f"Peak risk at **{_HORIZON_LABELS.get(selected_summary.get('peak_horizon','?'), '?')}** "
                f"({selected_summary.get('peak_pct', 0)}% probability)"
            )

        # Get full horizon detail for this supplier
        supplier_forecasts = [fc for fc in all_forecasts if fc.get("supplier_name") == selected_name]
        _render_supplier_horizons(supplier_forecasts)


def _render_heatmap(summary: list[dict], all_forecasts: list[dict]) -> None:
    """Show a compact table: rows = suppliers, columns = horizons, cells = % probability."""
    import pandas as pd

    horizons_order = list(_HORIZON_LABELS.keys())

    # Build pivot: supplier → horizon → pct
    pivot: dict[str, dict[str, int]] = {}
    for fc in all_forecasts:
        sn = fc.get("supplier_name", "?")
        h = fc.get("horizon", "?")
        pct = fc.get("disruption_pct", 0)
        pivot.setdefault(sn, {})[h] = pct

    if not pivot:
        st.info("No forecast data to display.")
        return

    rows = []
    for sn, by_horizon in pivot.items():
        row = {"Supplier": sn}
        for h in horizons_order:
            row[_HORIZON_LABELS[h]] = by_horizon.get(h, 0)
        rows.append(row)

    df = pd.DataFrame(rows).set_index("Supplier")

    def color_cell(val):
        if val >= 65:
            return "background-color:#f8d7da;color:#842029;font-weight:bold"
        if val >= 40:
            return "background-color:#fff3cd;color:#664d03;font-weight:bold"
        if val >= 20:
            return "background-color:#fffbcc;color:#555"
        return "background-color:#d1e7dd;color:#0f5132"

    styled = df.style.applymap(color_cell).format("{:.0f}%")
    st.dataframe(styled, use_container_width=True)
    st.caption("Cells show disruption probability %. 🟥 ≥65% · 🟧 40–65% · 🟨 20–40% · 🟩 <20%")


def _render_supplier_horizons(forecasts: list[dict]) -> None:
    if not forecasts:
        st.warning("No forecast data for this supplier. Run forecasts first.")
        return

    for fc in forecasts:
        h = fc.get("horizon", "?")
        prob = fc.get("disruption_probability", 0)
        conf = fc.get("confidence", "low")
        drivers = fc.get("drivers", [])
        scenario = fc.get("scenario", "")
        trend = fc.get("overall_trend", "stable")

        label = _HORIZON_LABELS.get(h, h)
        conf_icon = _CONFIDENCE_ICON.get(conf, "🔵")

        with st.expander(f"**{label}** — {conf_icon} {int(prob*100)}% disruption probability", expanded=(prob >= 0.4)):
            st.markdown(_prob_bar(prob), unsafe_allow_html=True)
            st.caption(f"Confidence: {conf_icon} {conf.title()}  ·  Trend: {_TREND_ICON.get(trend,'➡️')} {trend.title()}")

            if drivers:
                st.markdown("**Key Drivers**")
                for d in drivers:
                    st.markdown(f"  • {d}")

            if scenario:
                st.markdown("**Scenario**")
                st.info(scenario)
