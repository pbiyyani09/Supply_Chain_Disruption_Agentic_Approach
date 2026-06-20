"""Replay mode — date-range slider that replays historical events chronologically."""
from __future__ import annotations

from datetime import datetime

import plotly.express as px
import requests
import streamlit as st

API_BASE = "http://localhost:8000"


def render_replay(suppliers: list[dict]) -> None:
    st.subheader("Replay Mode")
    st.caption("Scrub through historical events to replay crisis scenarios.")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=datetime(2023, 12, 18).date())
    with col2:
        end_date = st.date_input("To", value=datetime(2024, 1, 6).date())

    if start_date >= end_date:
        st.warning("Start date must be before end date.")
        return

    if st.button("Load events in range"):
        try:
            resp = requests.get(
                f"{API_BASE}/events/range",
                params={
                    "start": datetime.combine(start_date, datetime.min.time()).isoformat(),
                    "end": datetime.combine(end_date, datetime.max.time()).isoformat(),
                },
                timeout=10,
            )
            events = resp.json() if resp.ok else []
        except Exception as exc:
            st.error(f"Could not reach API: {exc}")
            events = []

        if not events:
            st.info("No events found in this range. Try seeding demo data first (scripts/seed_demo.py).")
            return

        st.success(f"Loaded {len(events)} events from {start_date} → {end_date}")

        # Timeline chart
        import pandas as pd
        df = pd.DataFrame([
            {
                "date": e.get("published_at", "")[:10],
                "category": e.get("category", "unknown"),
                "headline": e.get("headline", "")[:60],
            }
            for e in events
        ])
        if not df.empty:
            fig = px.histogram(df, x="date", color="category", title="Events over time")
            st.plotly_chart(fig, use_container_width=True)

        # Event list
        for e in sorted(events, key=lambda x: x.get("published_at") or ""):
            pub = (e.get("published_at") or "")[:10]
            cat = e.get("category", "?").upper()
            countries = ", ".join(e.get("affected_countries", []))
            st.markdown(f"**{pub}** `[{cat}]` {e['headline']}  \n_{countries}_")


def render_risk_timeline(suppliers: list[dict], risk_scores: list[dict]) -> None:
    """Plotly line chart: x = last 7 days, y = max score per supplier."""
    import pandas as pd

    if not risk_scores:
        st.info("No risk scores yet.")
        return

    rows = []
    for rs in risk_scores:
        rows.append({
            "supplier": rs.get("supplier_name", rs.get("supplier_id", "?")),
            "date": str(rs.get("scored_at", ""))[:10],
            "score": rs.get("score", 0),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return

    fig = px.line(
        df.groupby(["date", "supplier"])["score"].max().reset_index(),
        x="date",
        y="score",
        color="supplier",
        title="Risk Score Over Time (7-day)",
        range_y=[0, 10],
    )
    st.plotly_chart(fig, use_container_width=True)
