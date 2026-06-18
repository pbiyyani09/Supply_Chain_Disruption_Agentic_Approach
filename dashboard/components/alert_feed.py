"""Alert feed component — sorted by severity, expandable briefs."""
from __future__ import annotations

import streamlit as st


_LEVEL_COLORS = {
    "HIGH": "🔴",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}


def render_alert_feed(alerts: list[dict]) -> None:
    if not alerts:
        st.info("No alerts yet. Run a scan or wait for the next scheduled check.")
        return

    for alert in alerts:
        level = alert.get("level", "LOW")
        icon = _LEVEL_COLORS.get(level, "⚪")
        supplier = alert.get("supplier_name", "Unknown supplier")
        country = alert.get("supplier_country", "")
        headline = alert.get("event_headline", "")
        score = alert.get("score")
        window = alert.get("impact_window", "")
        created = alert.get("created_at", "")

        header = f"{icon} **{level}** — {supplier} ({country}) | Score: {score}/10 | {window}"
        with st.expander(header, expanded=(level == "HIGH" and not alert.get("is_read"))):
            st.caption(f"Event: {headline}")
            st.caption(f"Category: {alert.get('event_category', '').title()} · Alerted: {str(created)[:16]}")

            if alert.get("brief"):
                st.markdown("**Brief**")
                st.write(alert["brief"])

            if alert.get("alternatives"):
                st.markdown(f"**Alternative regions:** {', '.join(alert['alternatives'])}")

            dispatched = alert.get("dispatched_via") or []
            if dispatched:
                st.caption(f"Dispatched via: {', '.join(dispatched)}")
