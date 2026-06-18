"""ChainWatch Streamlit Dashboard.

Tabs: Risk Map | Alert Feed | Timeline | Replay | Chat
"""
from __future__ import annotations

import requests
import streamlit as st

from dashboard.components.alert_feed import render_alert_feed
from dashboard.components.chat import render_chat
from dashboard.components.replay import render_replay, render_risk_timeline
from dashboard.components.risk_map import render_risk_map

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


def _top_events(events: list[dict], n: int = 5) -> list[dict]:
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(events, key=lambda e: severity_order.get(e.get("severity_hint", "low"), 3))[:n]


# ── Sidebar ────────────────────────────────────────────────────────────────────

def _render_sidebar(suppliers: list[dict], alerts: list[dict]) -> None:
    st.sidebar.title("⛓️ ChainWatch")
    st.sidebar.caption("Supply Chain Disruption Early Warning")

    # Unread count badge
    unread = sum(1 for a in alerts if not a.get("is_read"))
    if unread:
        st.sidebar.error(f"🔔 {unread} unread alert{'s' if unread > 1 else ''}")

    st.sidebar.divider()
    st.sidebar.subheader("Your Suppliers")
    if suppliers:
        for s in suppliers:
            st.sidebar.caption(f"• {s['name']} ({s['country_code']}, T{s['tier']})")
    else:
        st.sidebar.info("No suppliers loaded yet.")

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

    st.sidebar.divider()
    if st.sidebar.button("Run Manual Scan", use_container_width=True):
        with st.spinner("Scanning for new events..."):
            try:
                r = requests.post(f"{API_BASE}/scan", timeout=120)
                result = r.json()
                st.sidebar.success(
                    f"Scan complete — {result.get('scores_created', 0)} scores, "
                    f"{result.get('high_alerts_dispatched', 0)} HIGH alerts"
                )
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"Scan failed: {exc}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    suppliers = _get_suppliers()
    alerts = _get_alerts()
    events = _get_events()

    _render_sidebar(suppliers, alerts)

    st.title("ChainWatch — Supply Chain Risk Dashboard")

    # Derive risk scores from alerts for map coloring
    risk_scores_for_map = []
    for a in alerts:
        if a.get("score") is not None:
            # Find supplier id from suppliers list
            for s in suppliers:
                if s["name"] == a.get("supplier_name"):
                    risk_scores_for_map.append({"supplier_id": s["id"], "score": a["score"]})

    tab_map, tab_alerts, tab_timeline, tab_replay, tab_chat = st.tabs(
        ["🗺️ Risk Map", "🚨 Alerts", "📈 Timeline", "⏪ Replay", "💬 Chat"]
    )

    with tab_map:
        st.subheader("Supplier Risk Map")
        render_risk_map(suppliers, risk_scores_for_map)

    with tab_alerts:
        st.subheader("Alert Feed")
        render_alert_feed(alerts)

    with tab_timeline:
        st.subheader("Risk Score Timeline")
        render_risk_timeline(suppliers, [])  # TODO: wire in raw risk_scores endpoint

    with tab_replay:
        render_replay(suppliers)

    with tab_chat:
        render_chat(suppliers, _top_events(events), alerts[:20])


if __name__ == "__main__":
    main()
