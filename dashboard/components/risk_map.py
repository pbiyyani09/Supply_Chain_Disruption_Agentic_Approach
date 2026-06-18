"""Pydeck world map — supplier dots color-coded by current max risk level."""
from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st


def _risk_color(score: int) -> list[int]:
    if score >= 7:
        return [220, 53, 69, 200]   # red
    if score >= 4:
        return [255, 193, 7, 200]   # amber
    return [40, 167, 69, 200]       # green


def render_risk_map(suppliers: list[dict], risk_scores: list[dict]) -> None:
    """
    suppliers: list of supplier dicts with lat/lng
    risk_scores: list of risk score dicts with supplier_id and score
    """
    max_score: dict[str, int] = {}
    for rs in risk_scores:
        sid = rs.get("supplier_id") or rs.get("id", "")
        max_score[sid] = max(max_score.get(sid, 0), rs.get("score", 0))

    rows = []
    for s in suppliers:
        if s.get("lat") is None or s.get("lng") is None:
            continue
        score = max_score.get(s["id"], 0)
        rows.append({
            "name": s["name"],
            "lat": s["lat"],
            "lon": s["lng"],
            "score": score,
            "color": _risk_color(score),
            "tooltip": f"{s['name']} ({s['country_code']}) — Score: {score or 'N/A'}",
        })

    if not rows:
        st.info("No suppliers with geocoordinates to display. Upload your supplier CSV first.")
        return

    df = pd.DataFrame(rows)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=200000,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(latitude=20, longitude=15, zoom=1.5, pitch=0)

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{tooltip}"},
            map_style="mapbox://styles/mapbox/light-v9",
        )
    )
