"""Maritime Port Congestion Map — vessel congestion at strategic global ports."""
from __future__ import annotations

import os

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

_LEVEL_COLOR = {
    "HIGH":   [220, 53,  69,  230],
    "MEDIUM": [255, 165,  0,  210],
    "NORMAL": [40,  167,  69, 180],
}
_LEVEL_ICON = {"HIGH": "🔴", "MEDIUM": "🟡", "NORMAL": "🟢"}


@st.cache_data(ttl=300)
def _get_congestion(industry: str) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/maritime/congestion", params={"industry": industry}, timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []


def render_maritime_map(industry: str = "all") -> None:
    st.subheader("Port Congestion & Maritime Intelligence")

    vessel_key = os.getenv("VESSEL_API_KEY", "")
    if not vessel_key:
        st.warning(
            "**Demo Mode** — Real-time AIS data requires a free VesselAPI key.  \n"
            "Sign up at [vesselapi.com](https://vesselapi.com) (no credit card required), "
            "then add `VESSEL_API_KEY=<your_key>` to `.env` and restart the API."
        )

    ports = _get_congestion(industry)
    if not ports:
        st.info("No port data available.")
        return

    high_count = sum(1 for p in ports if p["level"] == "HIGH")
    med_count = sum(1 for p in ports if p["level"] == "MEDIUM")
    norm_count = sum(1 for p in ports if p["level"] == "NORMAL")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ports Monitored", len(ports))
    c2.metric("HIGH Congestion", high_count, delta=f"+{high_count}" if high_count else None, delta_color="inverse")
    c3.metric("MEDIUM Congestion", med_count)
    c4.metric("Normal", norm_count)

    # Pydeck map
    rows = []
    for p in ports:
        rows.append({
            "name": p["port_name"],
            "country": p["country"],
            "lat": p["lat"],
            "lon": p["lng"],
            "level": p["level"],
            "color": _LEVEL_COLOR.get(p["level"], [128, 128, 128, 180]),
            "vessels": p.get("vessels_at_anchor", 0),
            "index": p.get("congestion_index", 1.0),
            "tooltip": (
                f"{p['port_name']} ({p['country']})\n"
                f"Congestion: {p['level']}\n"
                f"Vessels at anchor: {p.get('vessels_at_anchor', '?')}\n"
                f"Index: {p.get('congestion_index', '?')}x normal"
                + (" [DEMO]" if p.get("is_demo") else "")
            ),
        })

    df = pd.DataFrame(rows)

    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=200000,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 100, 255],
    )

    labels = pdk.Layer(
        "TextLayer",
        data=df,
        get_position=["lon", "lat"],
        get_text="name",
        get_size=11,
        get_color=[30, 30, 30, 200],
        get_anchor="'middle'",
        get_alignment_baseline="'bottom'",
        get_pixel_offset=[0, -25],
    )

    m1, m2, m3, _ = st.columns([1, 1, 1, 4])
    m1.markdown("🔴 **HIGH**")
    m2.markdown("🟡 **MEDIUM**")
    m3.markdown("🟢 **Normal**")

    st.pydeck_chart(
        pdk.Deck(
            layers=[scatter, labels],
            initial_view_state=pdk.ViewState(latitude=20, longitude=20, zoom=1.5),
            tooltip={"text": "{tooltip}"},
            map_provider="carto",
            map_style="light",
        ),
        use_container_width=True,
        height=480,
    )

    # Table below map
    st.subheader("Port Congestion Details")
    display_df = pd.DataFrame([{
        "Port": p["port_name"],
        "Country": p["country"],
        "Status": f"{_LEVEL_ICON[p['level']]} {p['level']}",
        "Vessels at Anchor": p.get("vessels_at_anchor", "?"),
        "Congestion Index": f"{p.get('congestion_index', 1.0):.2f}x",
        "Demo": "Yes" if p.get("is_demo") else "No",
    } for p in sorted(ports, key=lambda p: p.get("congestion_index", 0), reverse=True)])

    st.dataframe(display_df, use_container_width=True, hide_index=True)
