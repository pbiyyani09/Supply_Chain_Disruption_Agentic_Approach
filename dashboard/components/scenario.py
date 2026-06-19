"""Scenario Builder — what-if disruption analysis powered by Gemini."""
from __future__ import annotations

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

_IMPACT_ICON = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}
_IMPACT_COLOR = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#ffc107",
    "low": "#28a745",
}

_SCENARIO_EXAMPLES = [
    "Taiwan is blockaded by China for 30 days",
    "Red Sea shipping corridor is completely closed for 60 days",
    "Major earthquake hits Taiwan with magnitude 7.5",
    "India bans all pharmaceutical API exports for 90 days",
    "US imposes 60% tariffs on all Chinese imports effective immediately",
    "Bangladesh floods shut down 80% of garment factories for 3 weeks",
    "Strait of Hormuz is closed by Iran for 2 weeks",
    "Ukraine war escalates — all Ukrainian grain exports halt for 6 months",
    "Major cyberattack takes down TSMC's fab operations for 2 weeks",
    "Saudi Arabia announces emergency 2 million bpd OPEC cut",
]


def render_scenario_builder(suppliers: list[dict], industry: str = "electronics") -> None:
    st.subheader("What-If Scenario Builder")
    st.caption(
        "Describe any disruption scenario in plain language. Gemini will analyze the impact "
        "on each of your suppliers and generate a structured response plan."
    )

    # ── Example scenarios ──────────────────────────────────────────────────────
    st.markdown("**Example scenarios — click to load:**")
    cols = st.columns(2)
    for i, ex in enumerate(_SCENARIO_EXAMPLES[:6]):
        with cols[i % 2]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state["scenario_input"] = ex

    st.divider()

    # ── Text input ─────────────────────────────────────────────────────────────
    scenario_text = st.text_area(
        "Describe your scenario",
        value=st.session_state.get("scenario_input", ""),
        height=100,
        placeholder="e.g. Taiwan is blockaded for 30 days...",
    )

    col_btn, col_clear = st.columns([1, 1])
    with col_btn:
        run_clicked = st.button("Analyze Scenario", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.pop("scenario_input", None)
            st.session_state.pop("scenario_result", None)
            st.rerun()

    if run_clicked and scenario_text.strip():
        with st.spinner("Gemini is analyzing impact across your supply chain..."):
            try:
                r = requests.post(
                    f"{API_BASE}/scenario",
                    params={"scenario": scenario_text, "industry": industry},
                    timeout=120,
                )
                if r.ok:
                    result = r.json()
                    st.session_state["scenario_result"] = result
                    st.session_state["scenario_input"] = scenario_text
                else:
                    st.error(f"Analysis failed: {r.text}")
            except Exception as exc:
                st.error(f"Could not reach API: {exc}")

    # ── Display results ────────────────────────────────────────────────────────
    result = st.session_state.get("scenario_result")
    if result:
        _render_result(result)


def _render_result(result: dict) -> None:
    st.divider()
    st.subheader("Scenario Analysis Results")

    # Summary
    st.info(f"**Scenario:** {result.get('scenario_summary', 'N/A')}")

    meta_col1, meta_col2, meta_col3 = st.columns(3)
    meta_col1.metric("Affected Suppliers", len(result.get("affected_suppliers", [])))
    meta_col2.metric("Unaffected Suppliers", len(result.get("unaffected_suppliers", [])))
    meta_col3.metric("Est. Recovery Time", result.get("time_to_recovery", "Unknown"))

    # Total impact narrative
    st.markdown("**Total Supply Chain Impact**")
    st.write(result.get("total_supply_chain_impact", ""))

    # Immediate actions
    st.markdown("**Recommended Immediate Actions**")
    for action in result.get("recommended_immediate_actions", []):
        st.markdown(f"- {action}")

    # Secondary risks
    if result.get("secondary_risks"):
        st.markdown("**Secondary Risks to Watch**")
        for risk in result["secondary_risks"]:
            st.markdown(f"- ⚠️ {risk}")

    st.divider()

    # Per-supplier breakdown
    affected = result.get("affected_suppliers", [])
    if affected:
        st.subheader("Affected Suppliers — Impact Breakdown")

        # Sort by impact severity
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        affected_sorted = sorted(affected, key=lambda s: sev_order.get(s.get("impact_severity", "low"), 4))

        for supplier in affected_sorted:
            sev = supplier.get("impact_severity", "low")
            icon = _IMPACT_ICON.get(sev, "⚪")
            name = supplier.get("supplier_name", "Unknown")
            country = supplier.get("country_code", "")
            duration = supplier.get("estimated_duration", "Unknown")
            revenue_risk = supplier.get("revenue_at_risk", "Unknown")

            with st.expander(
                f"{icon} **{name}** ({country}) — {sev.upper()} impact · {duration}",
                expanded=(sev in ("critical", "high")),
            ):
                col1, col2 = st.columns(2)
                col1.metric("Impact Severity", f"{icon} {sev.title()}")
                col2.metric("Revenue at Risk", revenue_risk.title())

                if score_uplift := supplier.get("score_uplift"):
                    st.caption(f"Risk score uplift: +{score_uplift} points on current score")

                st.markdown("**Mitigation Actions**")
                for action in supplier.get("mitigation_actions", []):
                    st.markdown(f"  ✓ {action}")

    # Unaffected suppliers
    unaffected = result.get("unaffected_suppliers", [])
    if unaffected:
        st.success(f"**Unaffected suppliers:** {', '.join(unaffected)}")
