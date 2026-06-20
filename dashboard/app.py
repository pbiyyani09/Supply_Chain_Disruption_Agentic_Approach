"""ChainWatch Streamlit Dashboard — v2.0

Tabs: Risk Map | Alerts | Timeline | Forecast | Signals | Maritime | Calendar | Scenarios | Replay | Chat
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import streamlit as st

from dashboard.components.alert_feed import render_alert_feed
from dashboard.components.chat import render_chat
from dashboard.components.economic_panel import render_economic_panel
from dashboard.components.forecast import render_forecast_tab
from dashboard.components.maritime_map import render_maritime_map
from dashboard.components.replay import render_replay, render_risk_timeline
from dashboard.components.risk_map import render_risk_map
from dashboard.components.scenario import render_scenario_builder
from dashboard.components.seasonal_calendar import render_seasonal_calendar
from data.industry_profiles import INDUSTRY_PROFILES, all_labels
from observability import setup_observability

# Trace the dashboard's own Gemini chat calls when PHOENIX_ENABLED=true.
# Safe no-op otherwise; runs before any chat call (which happens on user action).
setup_observability()

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="ChainWatch",
    page_icon="⛓️",
    layout="wide",
)


# ── Data fetchers ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _get_suppliers() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/suppliers/", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=60)
def _get_alerts() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/alerts/", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=60)
def _get_events(limit: int = 50) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/events/", params={"limit": limit}, timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=60)
def _get_risk_scores() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/risk-scores/", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def _top_events(events: list[dict], n: int = 5) -> list[dict]:
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(events, key=lambda e: severity_order.get(e.get("severity_hint", "low"), 3))[:n]


# ── Sidebar ────────────────────────────────────────────────────────────────────

def _render_sidebar(suppliers: list[dict], alerts: list[dict]) -> str:
    """Renders sidebar and returns the selected industry key."""
    st.sidebar.title("⛓️ ChainWatch")
    st.sidebar.caption("Supply Chain Disruption Early Warning v2.0")

    # Unread count badge
    unread = sum(1 for a in alerts if not a.get("is_read"))
    if unread:
        st.sidebar.error(f"🔔 {unread} unread alert{'s' if unread > 1 else ''}")

    # ── Industry selector ──────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Industry")
    labels = all_labels()
    keys = list(labels.keys())
    display_labels = list(labels.values())

    if "industry_key" not in st.session_state:
        st.session_state.industry_key = "electronics"

    selected_label = st.sidebar.selectbox(
        "Select your industry",
        options=display_labels,
        index=keys.index(st.session_state.industry_key),
        label_visibility="collapsed",
    )
    selected_key = keys[display_labels.index(selected_label)]

    if selected_key != st.session_state.industry_key:
        st.session_state.industry_key = selected_key
        st.rerun()

    profile = INDUSTRY_PROFILES[selected_key]
    st.sidebar.caption(f"_{profile['description']}_")
    st.sidebar.caption(
        f"**Key countries:** {', '.join(profile['key_countries'][:6])}"
    )
    st.sidebar.caption(
        f"**Watches:** {', '.join(profile['disruption_priorities'])}"
    )

    # ── Suppliers list ─────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Your Suppliers")
    if suppliers:
        for s in suppliers:
            st.sidebar.caption(f"• {s['name']} ({s['country_code']}, T{s['tier']})")
    else:
        st.sidebar.info("No suppliers loaded yet.")

    # ── CSV upload ─────────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Upload Suppliers")
    uploaded = st.sidebar.file_uploader("CSV file", type=["csv"], label_visibility="collapsed")
    if uploaded:
        resp = requests.post(
            f"{API_BASE}/suppliers/upload-csv",
            files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
            timeout=15,
        )
        if resp.ok:
            st.sidebar.success(f"Imported {resp.json()['imported']} suppliers!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.error(f"Upload failed: {resp.text}")

    # ── Manual scan ────────────────────────────────────────────────────────────
    st.sidebar.divider()
    if st.sidebar.button("Run Full Scan", use_container_width=True, type="primary"):
        with st.spinner(f"Running full pipeline for {selected_label}..."):
            try:
                r = requests.post(
                    f"{API_BASE}/scan",
                    params={"industry": selected_key},
                    timeout=300,
                )
                result = r.json()
                st.sidebar.success(
                    f"Scan complete — {result.get('new_events', 0)} events, "
                    f"{result.get('scores_created', 0)} scores, "
                    f"{result.get('high_alerts_dispatched', 0)} HIGH alerts, "
                    f"{result.get('forecasts_saved', 0)} forecasts"
                )
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"Scan failed: {exc}")

    return selected_key


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    suppliers = _get_suppliers()
    alerts = _get_alerts()
    events = _get_events()
    risk_scores = _get_risk_scores()

    selected_industry = _render_sidebar(suppliers, alerts)
    profile = INDUSTRY_PROFILES[selected_industry]

    st.title("ChainWatch — Supply Chain Risk Dashboard")
    st.caption(
        f"Monitoring **{profile['label']}** supply chains · "
        f"Key regions: {', '.join(profile['key_countries'][:6])} · "
        f"Priority disruptions: {', '.join(profile['disruption_priorities'])}"
    )

    (
        tab_map, tab_alerts, tab_timeline,
        tab_forecast, tab_signals, tab_maritime,
        tab_calendar, tab_scenarios, tab_replay, tab_chat
    ) = st.tabs([
        "🗺️ Risk Map",
        "🚨 Alerts",
        "📈 Timeline",
        "🔮 Forecast",
        "📊 Signals",
        "🚢 Maritime",
        "📅 Calendar",
        "🎭 Scenarios",
        "⏪ Replay",
        "💬 Chat",
    ])

    with tab_map:
        st.subheader(f"Supplier Risk Map — {profile['label']}")
        render_risk_map(suppliers, risk_scores, alerts)

    with tab_alerts:
        st.subheader("Alert Feed")
        render_alert_feed(alerts, industry=selected_industry)

    with tab_timeline:
        st.subheader("Risk Score Timeline")
        render_risk_timeline(suppliers, risk_scores)

    with tab_forecast:
        render_forecast_tab(suppliers, industry=selected_industry)

    with tab_signals:
        render_economic_panel(industry=selected_industry)

    with tab_maritime:
        render_maritime_map(industry=selected_industry)

    with tab_calendar:
        render_seasonal_calendar(industry=selected_industry)

    with tab_scenarios:
        render_scenario_builder(suppliers, industry=selected_industry)

    with tab_replay:
        render_replay(suppliers)

    with tab_chat:
        render_chat(suppliers, _top_events(events), alerts[:20])


if __name__ == "__main__":
    main()
