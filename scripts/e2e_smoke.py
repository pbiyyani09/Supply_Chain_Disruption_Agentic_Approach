"""End-to-end smoke test against a running ChainWatch stack (Docker or local).

Usage (with the stack up via `docker compose up`):

    python -m scripts.e2e_smoke                 # structural checks (no LLM needed)
    RUN_SCAN=1 python -m scripts.e2e_smoke      # also POST /scan (needs GOOGLE_API_KEY)

Exits non-zero on failure so it can gate a Docker E2E job.
"""
from __future__ import annotations

import os
import sys
import time

import requests

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
_SCAN_KEYS = {
    "new_events",
    "economic_signals_updated",
    "weather_events_checked",
    "scores_created",
    "high_alerts_dispatched",
    "forecasts_saved",
}


def _wait_for_health(timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{API_BASE}/health", timeout=5)
            if r.ok and r.json().get("status") == "ok":
                print(f"[e2e] /health OK — version {r.json().get('version')}")
                return
        except Exception as exc:  # noqa: BLE001 - retry loop
            last = exc
        time.sleep(2)
    raise SystemExit(f"[e2e] API did not become healthy in {timeout}s (last: {last})")


def _check_endpoints() -> None:
    for path in ("/suppliers/", "/events/", "/alerts/", "/forecasts/", "/economic-signals/"):
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        assert r.ok, f"[e2e] GET {path} -> {r.status_code}"
        assert isinstance(r.json(), list), f"[e2e] {path} did not return a list"
        print(f"[e2e] GET {path} OK ({len(r.json())} items)")


def _run_scan() -> None:
    print("[e2e] POST /scan (this exercises the full LangGraph pipeline)...")
    r = requests.post(f"{API_BASE}/scan", params={"industry": "electronics"}, timeout=600)
    assert r.ok, f"[e2e] POST /scan -> {r.status_code}: {r.text[:200]}"
    body = r.json()
    missing = _SCAN_KEYS - set(body)
    assert not missing, f"[e2e] /scan response missing keys: {missing}"
    print(f"[e2e] /scan OK — {body}")


def main() -> None:
    _wait_for_health()
    _check_endpoints()
    if os.getenv("RUN_SCAN", "").lower() in {"1", "true", "yes"}:
        _run_scan()
    else:
        print("[e2e] Skipping POST /scan (set RUN_SCAN=1 with a GOOGLE_API_KEY to include it)")
    print("[e2e] PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(exc)
        sys.exit(1)
