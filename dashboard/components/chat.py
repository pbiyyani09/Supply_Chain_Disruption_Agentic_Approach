"""Conversational Q&A component powered by Gemini with live data context injection."""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_CHAT_PROMPT_TEMPLATE = (Path(__file__).parent.parent.parent / "prompts" / "chat_context.txt").read_text()

_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _build_system_prompt(suppliers: list[dict], top_events: list[dict], recent_alerts: list[dict]) -> str:
    supplier_lines = "\n".join(
        f"- {s['name']} ({s['country_code']}, Tier {s['tier']}, {s['product_category']})"
        for s in suppliers
    )
    event_lines = "\n".join(
        f"- [{e.get('category','?').upper()}] {e.get('headline','')} "
        f"(countries: {', '.join(e.get('affected_countries', []))})"
        for e in top_events
    )
    alert_lines = "\n".join(
        f"- {a.get('level','?')} | {a.get('supplier_name','?')} | Score {a.get('score','?')}/10 "
        f"| {a.get('impact_window','?')} | {a.get('event_headline','')[:80]}"
        for a in recent_alerts
    )

    return _CHAT_PROMPT_TEMPLATE.format(
        supplier_list=supplier_lines or "(none loaded yet)",
        top_events=event_lines or "(no events yet)",
        recent_alerts=alert_lines or "(no alerts yet)",
    )


def _ask_gemini(system_prompt: str, history: list[dict], user_message: str) -> str:
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    try:
        response = _client.models.generate_content(
            model=_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                max_output_tokens=1024,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        return f"Error contacting Gemini: {exc}"


def render_chat(suppliers: list[dict], top_events: list[dict], recent_alerts: list[dict]) -> None:
    st.subheader("Ask ChainWatch")
    st.caption("Ask questions about your supplier risk data. Answers are grounded in live data only.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("e.g. Which supplier is most exposed to the Red Sea situation?")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        system_prompt = _build_system_prompt(suppliers, top_events, recent_alerts)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = _ask_gemini(system_prompt, st.session_state.chat_history[:-1], user_input)
            st.write(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})

    if st.session_state.chat_history:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()
