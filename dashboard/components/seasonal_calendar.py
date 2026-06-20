"""Seasonal Risk Calendar — upcoming disruption windows by industry."""
from __future__ import annotations

import os
from datetime import date

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

_SEV_COLOR = {"high": "#dc3545", "medium": "#fd7e14", "low": "#28a745"}
_SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
_TYPE_ICON = {
    "weather": "🌊",
    "geopolitical": "⚔️",
    "logistics": "🚢",
    "labor": "👷",
    "cyber": "💻",
}


@st.cache_data(ttl=3600)
def _get_upcoming(industry: str) -> list[dict]:
    try:
        r = requests.get(
            f"{API_BASE}/seasonal-risks/upcoming",
            params={"industry": industry, "look_ahead_months": 12},
            timeout=5,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=3600)
def _get_active(industry: str) -> list[dict]:
    try:
        r = requests.get(
            f"{API_BASE}/seasonal-risks/active",
            params={"industry": industry},
            timeout=5,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


def render_seasonal_calendar(industry: str = "all") -> None:
    st.subheader("Seasonal Risk Calendar")
    st.caption(
        "Recurring annual risk windows — predictable disruptions driven by weather, geopolitics, "
        "and operational patterns. Use this to build inventory buffers before windows open."
    )

    active = _get_active(industry)
    upcoming = _get_upcoming(industry)

    # ── Active now ─────────────────────────────────────────────────────────────
    if active:
        st.subheader("Currently Active Risk Windows")
        for w in active:
            sev = w.get("severity", "medium")
            icon = _SEV_ICON[sev]
            type_icon = _TYPE_ICON.get(w.get("risk_type", ""), "⚠️")
            countries = ", ".join(w.get("region_codes", [])[:6])
            with st.expander(f"{icon} {type_icon} **{w['title']}** — ACTIVE NOW ({sev.upper()} severity)", expanded=True):
                st.write(w.get("description", ""))
                st.caption(f"Regions: {countries} · Type: {w.get('risk_type', '?').title()}")
    else:
        st.success("No active seasonal risk windows for this industry right now.")

    st.divider()

    # ── Gantt-style timeline ───────────────────────────────────────────────────
    st.subheader("12-Month Outlook")

    if not upcoming:
        st.info("No seasonal risk data. This is unexpected — check API connectivity.")
        return

    # Build Plotly Gantt
    today = date.today()
    gantt_rows = []
    for w in upcoming:
        gantt_rows.append({
            "Task": w["title"][:50],
            "Start": w.get("next_start", str(today)),
            "Finish": w.get("next_end", str(today)),
            "Severity": w.get("severity", "medium").title(),
            "Type": w.get("risk_type", "other").title(),
            "Description": w.get("description", "")[:100],
            "Starts In": f"{w.get('starts_in_days', 0)} days",
        })

    if not gantt_rows:
        return

    df = pd.DataFrame(gantt_rows)

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Severity",
        color_discrete_map={"High": "#dc3545", "Medium": "#fd7e14", "Low": "#28a745"},
        hover_data=["Type", "Description", "Starts In"],
        title="Seasonal Risk Windows — Next 12 Months",
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=max(400, len(gantt_rows) * 35),
        showlegend=True,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Upcoming list (next 90 days) ───────────────────────────────────────────
    st.subheader("Next 90 Days — Upcoming Windows")
    near_term = [w for w in upcoming if 0 <= w.get("starts_in_days", 999) <= 90]
    if not near_term:
        st.success("No new seasonal risk windows opening in the next 90 days.")
    else:
        for w in near_term:
            sev = w.get("severity", "medium")
            icon = _SEV_ICON[sev]
            type_icon = _TYPE_ICON.get(w.get("risk_type", ""), "⚠️")
            days = w.get("starts_in_days", 0)
            countries = ", ".join(w.get("region_codes", [])[:5])

            with st.expander(
                f"{icon} {type_icon} **{w['title']}** — starts in {days} days ({w.get('next_start', '?')})",
                expanded=(sev == "high" and days <= 30),
            ):
                st.write(w.get("description", ""))
                st.caption(f"Regions: {countries}  ·  Window: {w.get('next_start','')} → {w.get('next_end','')}")

                # Procurement recommendation
                if sev == "high" and days <= 60:
                    st.warning(
                        f"**Procurement Action:** Build 60–90 day buffer inventory for suppliers in {countries} before this window opens."
                    )
                elif sev == "medium" and days <= 45:
                    st.info(
                        f"**Procurement Action:** Review supplier safety stock levels in {countries}. Consider 30-day buffer build."
                    )
