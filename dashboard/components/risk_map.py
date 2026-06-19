"""Pydeck world map — supplier dots color-coded by risk level with rich hover tooltips."""
from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st


def _risk_color(score: int) -> list[int]:
    if score >= 7:
        return [220, 53, 69, 230]    # red
    if score >= 4:
        return [255, 165, 0, 230]    # amber
    return [40, 200, 100, 200]       # green


def _build_tooltip(supplier: dict, score: int, best_score_record: dict | None, best_alert: dict | None) -> str:
    lines = [f"{supplier['name']} ({supplier['country_code']})"]
    lines.append(f"Category: {supplier.get('product_category', 'N/A')}  |  Tier {supplier.get('tier', '?')}")

    if score == 0:
        lines.append("Status: No active risk signals")
    else:
        level = "HIGH" if score >= 7 else ("MEDIUM" if score >= 4 else "LOW")
        lines.append(f"Risk Score: {score}/10  [{level}]")

        if best_score_record:
            lines.append(f"Impact window: {best_score_record.get('impact_window', 'unknown')}")
            reasoning = best_score_record.get("reasoning", "")
            if reasoning:
                # Wrap to ~60 chars
                words = reasoning.split()
                line, wrapped = "", []
                for w in words:
                    if len(line) + len(w) + 1 > 60:
                        wrapped.append(line.strip())
                        line = w + " "
                    else:
                        line += w + " "
                if line.strip():
                    wrapped.append(line.strip())
                lines.append("Why: " + "\n     ".join(wrapped))

        if best_alert:
            headline = best_alert.get("event_headline", "")
            if headline:
                lines.append(f"Event: {headline[:70]}")
            alts = best_alert.get("alternatives", [])
            if alts:
                lines.append(f"Alternatives: {', '.join(alts[:2])}")

    return "\n".join(lines)


def render_risk_map(suppliers: list[dict], risk_scores: list[dict], alerts: list[dict] = None) -> None:
    alerts = alerts or []

    # Index risk scores and alerts by supplier_id
    scores_by_supplier: dict[str, list[dict]] = {}
    for rs in risk_scores:
        sid = rs.get("supplier_id", "")
        scores_by_supplier.setdefault(sid, []).append(rs)

    alerts_by_supplier: dict[str, list[dict]] = {}
    for a in alerts:
        # match alert to supplier via supplier_name
        for s in suppliers:
            if s["name"] == a.get("supplier_name"):
                alerts_by_supplier.setdefault(s["id"], []).append(a)
                break

    rows = []
    for s in suppliers:
        if s.get("lat") is None or s.get("lng") is None:
            continue

        sid = s["id"]
        supplier_scores = scores_by_supplier.get(sid, [])
        max_score = max((r.get("score", 0) for r in supplier_scores), default=0)
        best_score_record = max(supplier_scores, key=lambda r: r.get("score", 0)) if supplier_scores else None
        best_alert = alerts_by_supplier.get(sid, [None])[0]

        tooltip = _build_tooltip(s, max_score, best_score_record, best_alert)

        label = s["name"].split()[0]  # first word fits on map
        score_label = f"{max_score}/10" if max_score else ""

        rows.append({
            "name": s["name"],
            "lat": s["lat"],
            "lon": s["lng"],
            "score": max_score,
            "color": _risk_color(max_score),
            "label": label,
            "score_label": score_label,
            "tooltip": tooltip,
        })

    if not rows:
        st.info("No suppliers with geocoordinates. Upload your supplier CSV first.")
        return

    df = pd.DataFrame(rows)
    df_scored = df[df["score"] > 0]
    df_safe = df[df["score"] == 0]

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=280000,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 100, 255],
    )

    # Name labels for all suppliers
    name_layer = pdk.Layer(
        "TextLayer",
        data=df,
        get_position=["lon", "lat"],
        get_text="label",
        get_size=12,
        get_color=[40, 40, 40, 220],
        get_anchor="'middle'",
        get_alignment_baseline="'bottom'",
        get_pixel_offset=[0, -22],
    )

    # Score badges only for suppliers with a score
    score_layer = pdk.Layer(
        "TextLayer",
        data=df_scored,
        get_position=["lon", "lat"],
        get_text="score_label",
        get_size=11,
        get_color=[180, 60, 0, 255],
        get_anchor="'middle'",
        get_alignment_baseline="'top'",
        get_pixel_offset=[0, 18],
    )

    view_state = pdk.ViewState(latitude=20, longitude=20, zoom=1.5, pitch=0)

    col1, col2, col3, _ = st.columns([1, 1, 1, 4])
    col1.markdown("🔴 **HIGH** ≥7")
    col2.markdown("🟠 **MED** 4–6")
    col3.markdown("🟢 **Safe** <4")

    st.pydeck_chart(
        pdk.Deck(
            layers=[scatter_layer, name_layer, score_layer],
            initial_view_state=view_state,
            tooltip={"text": "{tooltip}"},
            map_provider="carto",
            map_style="light",
        ),
        use_container_width=True,
        height=520,
    )
