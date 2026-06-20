"""Agent 4 — Alert Dispatcher.

Formats and dispatches HIGH alerts to Slack and Gmail.
Applies a 24-hour per-supplier/category cooldown to prevent spam.
No LLM required — pure dispatch logic.

Gmail replaces SendGrid (Google ecosystem; free quota is ample for demos).
"""
from __future__ import annotations

import base64
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk.webhook import WebhookClient
from sqlalchemy.orm import Session

from db.crud import alert_in_cooldown, create_alert
from db.models import Alert, Event, RiskScore, Supplier

load_dotenv()
logger = logging.getLogger(__name__)

COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", "24"))
HIGH_RISK_THRESHOLD = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))

_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_GMAIL_SENDER = os.getenv("GMAIL_SENDER_EMAIL", "")
_ALERT_RECIPIENT = os.getenv("ALERT_EMAIL_RECIPIENT", "")
_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")


# ── Slack ──────────────────────────────────────────────────────────────────────

def _send_slack(alert: Alert, risk_score: RiskScore) -> bool:
    if not _SLACK_WEBHOOK:
        logger.warning("[Dispatcher] SLACK_WEBHOOK_URL not set — skipping Slack")
        return False

    event: Event = risk_score.event
    supplier: Supplier = risk_score.supplier
    level_emoji = {"HIGH": ":red_circle:", "MEDIUM": ":large_yellow_circle:", "LOW": ":large_green_circle:"}.get(
        alert.level, ":white_circle:"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{level_emoji} ChainWatch {alert.level} ALERT — {supplier.name}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Score:* {risk_score.score}/10"},
                {"type": "mrkdwn", "text": f"*Impact window:* {risk_score.impact_window}"},
                {"type": "mrkdwn", "text": f"*Supplier:* {supplier.name} ({supplier.country_code})"},
                {"type": "mrkdwn", "text": f"*Category:* {event.category.title()}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Event:* {event.headline}"},
        },
    ]

    if alert.brief:
        # Show first paragraph of brief
        first_para = alert.brief.split("\n\n")[0]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Brief:*\n{first_para}"},
        })

    if alert.alternatives:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Alternative regions:* {', '.join(alert.alternatives)}",
            },
        })

    try:
        client = WebhookClient(_SLACK_WEBHOOK)
        resp = client.send(blocks=blocks)
        if resp.status_code == 200:
            logger.info("[Dispatcher] Slack alert sent for %s", supplier.name)
            return True
        logger.error("[Dispatcher] Slack error %d: %s", resp.status_code, resp.body)
        return False
    except Exception as exc:
        logger.error("[Dispatcher] Slack send failed: %s", exc)
        return False


# ── Gmail ──────────────────────────────────────────────────────────────────────

def _get_gmail_service():
    """Build Gmail API service using OAuth2 credentials."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        token_path = Path("token.json")
        creds = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif Path(_CREDENTIALS_FILE).exists():
                flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                token_path.write_text(creds.to_json())
            else:
                logger.warning("[Dispatcher] Gmail credentials not found — skipping email")
                return None

        return build("gmail", "v1", credentials=creds)
    except Exception as exc:
        logger.error("[Dispatcher] Gmail service init failed: %s", exc)
        return None


def _send_gmail(alert: Alert, risk_score: RiskScore) -> bool:
    if not _GMAIL_SENDER or not _ALERT_RECIPIENT:
        logger.warning("[Dispatcher] Gmail sender/recipient not configured — skipping email")
        return False

    service = _get_gmail_service()
    if not service:
        return False

    event: Event = risk_score.event
    supplier: Supplier = risk_score.supplier

    subject = f"[ChainWatch {alert.level}] {supplier.name} — {event.category.title()} Risk (Score: {risk_score.score}/10)"
    body_lines = [
        "ChainWatch Supply Chain Alert",
        f"{'='*50}",
        "",
        f"Supplier: {supplier.name} ({supplier.country_code})",
        f"Risk Score: {risk_score.score}/10",
        f"Impact Window: {risk_score.impact_window}",
        f"Alert Level: {alert.level}",
        f"Event: {event.headline}",
        "",
        "--- BRIEF ---",
        alert.brief or risk_score.reasoning,
        "",
    ]
    if alert.alternatives:
        body_lines.append(f"Alternative regions: {', '.join(alert.alternatives)}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _GMAIL_SENDER
    msg["To"] = _ALERT_RECIPIENT
    msg.attach(MIMEText("\n".join(body_lines), "plain"))

    try:
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info("[Dispatcher] Gmail alert sent for %s", supplier.name)
        return True
    except Exception as exc:
        logger.error("[Dispatcher] Gmail send failed: %s", exc)
        return False


# ── Main dispatch ──────────────────────────────────────────────────────────────

def dispatch_alert(
    db: Session,
    risk_score: RiskScore,
    brief: str,
    alternatives: list[str],
) -> Alert | None:
    """Check cooldown, create alert record, and dispatch to all channels."""
    event: Event = risk_score.event
    supplier: Supplier = risk_score.supplier

    if alert_in_cooldown(db, supplier.id, event.category, COOLDOWN_HOURS):
        logger.info(
            "[Dispatcher] Cooldown active for %s / %s — skipping",
            supplier.name,
            event.category,
        )
        return None

    score = risk_score.score
    level = "HIGH" if score >= HIGH_RISK_THRESHOLD else ("MEDIUM" if score >= 4 else "LOW")

    alert_data = {
        "risk_score_id": risk_score.id,
        "level": level,
        "brief": brief,
        "alternatives": alternatives,
        "dispatched_via": [],
        "is_read": False,
    }
    alert = create_alert(db, alert_data)

    channels: list[str] = []
    if _send_slack(alert, risk_score):
        channels.append("slack")
    if _send_gmail(alert, risk_score):
        channels.append("email")

    alert.dispatched_via = channels
    db.commit()
    db.refresh(alert)
    return alert
