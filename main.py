"""Placeholder module entry point.

The real entry points are the FastAPI backend (``api.main``) and the Streamlit
dashboard (``dashboard.app``). See README / CLAUDE.md for run commands.
"""


def main() -> None:
    """Print a hint pointing at the real entry points."""
    print("Run the API: `uvicorn api.main:app` — or the dashboard: `streamlit run dashboard/app.py`")


if __name__ == "__main__":
    main()
