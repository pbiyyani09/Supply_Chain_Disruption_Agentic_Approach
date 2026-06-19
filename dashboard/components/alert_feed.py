"""Alert feed component — sorted by severity, expandable briefs with response playbooks."""
from __future__ import annotations

import streamlit as st

from data.playbooks import get_playbook

_LEVEL_COLORS = {
    "HIGH": "🔴",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}


def render_alert_feed(alerts: list[dict], industry: str = "electronics") -> None:
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
        risk_type = alert.get("event_category", "logistics")

        header = f"{icon} **{level}** — {supplier} ({country}) | Score: {score}/10 | {window}"
        with st.expander(header, expanded=(level == "HIGH" and not alert.get("is_read"))):
            st.caption(f"Event: {headline}")
            st.caption(f"Category: {risk_type.title()} · Alerted: {str(created)[:16]}")

            if alert.get("brief"):
                st.markdown("**Gemini Brief**")
                st.write(alert["brief"])

            if alert.get("alternatives"):
                st.markdown(f"**Alternative sourcing regions:** {', '.join(alert['alternatives'])}")

            dispatched = alert.get("dispatched_via") or []
            if dispatched:
                st.caption(f"Dispatched via: {', '.join(dispatched)}")

            # ── Response Playbook ──────────────────────────────────────────────
            if level in ("HIGH", "MEDIUM"):
                with st.expander("Response Playbook", expanded=(level == "HIGH")):
                    steps = get_playbook(industry, risk_type)
                    st.caption(f"Industry: {industry.replace('_', ' ').title()} · Risk type: {risk_type.title()}")
                    for i, step in enumerate(steps, 1):
                        st.checkbox(step, key=f"playbook_{alert.get('id', '')}_{i}", value=False)
