"""Email notification channel for Veltrix.

Sends alerts and reports via SMTP email.
Supports TLS/SSL and authentication.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .db import now_iso


# SMTP Configuration from environment
SMTP_HOST = os.getenv("OUTPANEL_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("OUTPANEL_SMTP_PORT", "587"))
SMTP_USER = os.getenv("OUTPANEL_SMTP_USER", "").strip()
SMTP_PASS = os.getenv("OUTPANEL_SMTP_PASS", "").strip()
SMTP_FROM = os.getenv("OUTPANEL_SMTP_FROM", "").strip() or SMTP_USER
SMTP_TLS = os.getenv("OUTPANEL_SMTP_TLS", "1").strip() != "0"


def is_email_configured() -> bool:
    """Check if SMTP is configured."""
    return bool(SMTP_HOST and SMTP_FROM)


def send_email(to: str, subject: str, body_html: str, body_text: str = "") -> None:
    """Send an email via SMTP.

    Args:
        to: Recipient email address
        subject: Email subject
        body_html: HTML body content
        body_text: Plain text fallback (optional)
    """
    if not is_email_configured():
        raise ValueError("SMTP is not configured. Set OUTPANEL_SMTP_HOST and OUTPANEL_SMTP_FROM.")

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg["X-Mailer"] = "Veltrix/0.3.0"

    # Plain text part
    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # HTML part
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # Connect and send
    try:
        if SMTP_PORT == 465:
            # SSL
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as server:
                if SMTP_USER and SMTP_PASS:
                    server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            # STARTTLS
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                if SMTP_TLS:
                    server.starttls(context=ssl.create_default_context())
                if SMTP_USER and SMTP_PASS:
                    server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
    except smtplib.SMTPException as exc:
        raise ValueError(f"SMTP error: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Connection error: {exc}") from exc


def send_alert_email(to: str, alert_message: str, server_name: str = "", severity: str = "warning") -> None:
    """Send an alert notification email."""
    color = "#c0392b" if severity == "critical" else "#c27c0e"
    subject = f"[Veltrix] {'CRITICAL' if severity == 'critical' else 'Warning'}: {server_name or 'Alert'}"

    html = f"""
    <div style="font-family:Tahoma,Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <div style="background:#071013;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#19f1d2;margin:0;font-size:24px;">Veltrix</h1>
            <p style="color:#8fa3a0;margin:5px 0 0;font-size:12px;">Intelligent Network Control</p>
        </div>
        <div style="border:1px solid #dce5e2;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
            <div style="border-right:4px solid {color};padding:12px 16px;background:#f9f9f9;border-radius:4px;margin-bottom:16px;">
                <strong style="color:{color};">{severity.upper()}</strong>
                <p style="margin:8px 0 0;color:#333;">{alert_message}</p>
            </div>
            <p style="color:#666;font-size:13px;">Server: {server_name or 'N/A'}</p>
            <p style="color:#666;font-size:13px;">Time: {now_iso()}</p>
            <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
            <p style="color:#999;font-size:11px;text-align:center;">
                This alert was sent by Veltrix. Login to your dashboard for details.
            </p>
        </div>
    </div>
    """

    send_email(to, subject, html, body_text=f"[{severity.upper()}] {alert_message}\nServer: {server_name}\nTime: {now_iso()}")


def send_report_email(to: str, report_summary: dict[str, Any]) -> None:
    """Send a weekly report email."""
    subject = "[Veltrix] Weekly Uptime Report"
    avg = report_summary.get("average_availability", 0)
    total_servers = report_summary.get("total_servers", 0)
    incidents = report_summary.get("total_incidents", 0)

    html = f"""
    <div style="font-family:Tahoma,Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <div style="background:#071013;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#19f1d2;margin:0;font-size:24px;">Veltrix</h1>
            <p style="color:#8fa3a0;margin:5px 0 0;font-size:12px;">Weekly Report</p>
        </div>
        <div style="border:1px solid #dce5e2;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
                <tr>
                    <td style="padding:12px;background:#f0faf7;border-radius:4px;text-align:center;">
                        <strong style="font-size:28px;color:#058274;">{avg}%</strong><br>
                        <span style="color:#666;font-size:12px;">Avg Availability</span>
                    </td>
                    <td style="padding:12px;background:#f0faf7;border-radius:4px;text-align:center;">
                        <strong style="font-size:28px;color:#058274;">{total_servers}</strong><br>
                        <span style="color:#666;font-size:12px;">Servers</span>
                    </td>
                    <td style="padding:12px;background:#f0faf7;border-radius:4px;text-align:center;">
                        <strong style="font-size:28px;color:#c27c0e;">{incidents}</strong><br>
                        <span style="color:#666;font-size:12px;">Incidents</span>
                    </td>
                </tr>
            </table>
            <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
            <p style="color:#999;font-size:11px;text-align:center;">
                Login to your Veltrix dashboard for the full report.
            </p>
        </div>
    </div>
    """

    send_email(to, subject, html, body_text=f"Weekly Report\nAvailability: {avg}%\nServers: {total_servers}\nIncidents: {incidents}")
