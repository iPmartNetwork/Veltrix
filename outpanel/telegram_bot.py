"""Two-way Telegram Bot for Veltrix.

Allows operators to check server status, run pings, and receive alerts
directly from Telegram without opening the dashboard.

Commands:
  /status       — Overview of all servers
  /servers      — List servers with status
  /server <id>  — Detail of a specific server
  /ping <id>    — Ping all outbounds of a server
  /alerts       — Active alerts
  /incidents    — Open incidents
  /health       — Health scores
  /help         — Show available commands
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from .db import connect, now_iso, rows_to_dicts
from .monitor import calculate_health_score


# Configuration
BOT_TOKEN = os.getenv("OUTPANEL_TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_IDS = set(
    cid.strip() for cid in os.getenv("OUTPANEL_TELEGRAM_ALLOWED_CHATS", "").split(",") if cid.strip()
)
POLL_INTERVAL = int(os.getenv("OUTPANEL_TELEGRAM_POLL_INTERVAL", "3"))


def is_bot_enabled() -> bool:
    """Check if the Telegram bot is configured."""
    return bool(BOT_TOKEN)


def is_chat_allowed(chat_id: str) -> bool:
    """Check if a chat ID is allowed to use the bot."""
    if not ALLOWED_CHAT_IDS:
        return True  # No restriction if not configured
    return str(chat_id) in ALLOWED_CHAT_IDS


def bot_polling_loop(stop_event: threading.Event) -> None:
    """Long-polling loop for Telegram bot updates."""
    if not is_bot_enabled():
        return

    offset = 0
    while not stop_event.is_set():
        try:
            updates = get_updates(offset, timeout=POLL_INTERVAL)
            for update in updates:
                offset = update.get("update_id", 0) + 1
                process_update(update)
        except Exception:
            pass
        stop_event.wait(1)


def get_updates(offset: int, timeout: int = 3) -> list[dict[str, Any]]:
    """Fetch updates from Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = f"?offset={offset}&timeout={timeout}&allowed_updates=[\"message\"]"
    request = urllib.request.Request(url + params)
    try:
        with urllib.request.urlopen(request, timeout=timeout + 5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
    except Exception:
        pass
    return []


def process_update(update: dict[str, Any]) -> None:
    """Process a single Telegram update."""
    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text or not chat_id:
        return

    if not is_chat_allowed(chat_id):
        send_message(chat_id, "⛔ دسترسی شما به این ربات مجاز نیست.")
        return

    # Parse command
    command = text.split()[0].lower().replace("@", "").split("@")[0]
    args = text.split()[1:] if len(text.split()) > 1 else []

    handlers = {
        "/start": cmd_help,
        "/help": cmd_help,
        "/status": cmd_status,
        "/servers": cmd_servers,
        "/server": cmd_server_detail,
        "/ping": cmd_ping,
        "/alerts": cmd_alerts,
        "/incidents": cmd_incidents,
        "/health": cmd_health,
    }

    handler = handlers.get(command)
    if handler:
        try:
            response_text = handler(args)
            send_message(chat_id, response_text)
        except Exception as exc:
            send_message(chat_id, f"❌ خطا: {str(exc)[:200]}")
    elif text.startswith("/"):
        send_message(chat_id, "❓ دستور ناشناخته. /help را ببینید.")


def send_message(chat_id: str, text: str) -> None:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

def cmd_help(args: list[str]) -> str:
    return """🤖 <b>Veltrix Bot</b> — کنترل هوشمند شبکه

<b>دستورات:</b>
/status — نمای کلی
/servers — لیست سرورها
/server &lt;id&gt; — جزئیات سرور
/ping &lt;id&gt; — تست پینگ اوت‌باندها
/alerts — اعلان‌های فعال
/incidents — رخدادهای باز
/health — امتیاز سلامت
/help — راهنما"""


def cmd_status(args: list[str]) -> str:
    with connect() as conn:
        servers = conn.execute("SELECT COUNT(*) as c FROM servers").fetchone()["c"]
        online = conn.execute("SELECT COUNT(*) as c FROM servers WHERE enabled=1 AND last_status='online'").fetchone()["c"]
        outbounds = conn.execute("SELECT COUNT(*) as c FROM outbounds").fetchone()["c"]
        alerts = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE active=1").fetchone()["c"]
        incidents = conn.execute("SELECT COUNT(*) as c FROM incidents WHERE status IN ('open','acknowledged')").fetchone()["c"]

    return f"""📊 <b>وضعیت Veltrix</b>

🖥 سرورها: {servers} ({online} آنلاین)
🔗 اوت‌باندها: {outbounds}
⚠️ اعلان فعال: {alerts}
🔴 رخداد باز: {incidents}

⏰ {now_iso()[:16]}"""


def cmd_servers(args: list[str]) -> str:
    with connect() as conn:
        servers = rows_to_dicts(conn.execute(
            "SELECT id, name, host, enabled, last_status FROM servers ORDER BY id LIMIT 20"
        ).fetchall())

    if not servers:
        return "📭 هنوز سروری ثبت نشده."

    lines = ["🖥 <b>سرورها:</b>\n"]
    for s in servers:
        status = s["last_status"] if s["enabled"] else "disabled"
        icon = {"online": "🟢", "error": "🔴", "disabled": "⚪"}.get(status, "🟡")
        lines.append(f"{icon} <code>{s['id']}</code> {s['name']} — {s['host']}")

    return "\n".join(lines)


def cmd_server_detail(args: list[str]) -> str:
    if not args:
        return "❓ استفاده: /server <id>"

    try:
        server_id = int(args[0])
    except ValueError:
        return "❓ شناسه سرور باید عدد باشد."

    with connect() as conn:
        server = conn.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
        if not server:
            return "❌ سرور یافت نشد."

        outbound_count = conn.execute(
            "SELECT COUNT(*) as c FROM outbounds WHERE server_id=?", (server_id,)
        ).fetchone()["c"]

        metric = conn.execute(
            "SELECT cpu_percent, ram_percent, xray_status, uptime FROM metrics WHERE server_id=? ORDER BY created_at DESC LIMIT 1",
            (server_id,),
        ).fetchone()

    health = calculate_health_score(server_id)
    status_icon = {"online": "🟢", "error": "🔴", "disabled": "⚪"}.get(server["last_status"], "🟡")

    text = f"""{status_icon} <b>{server['name']}</b>

📍 Host: <code>{server['host']}</code>
📊 وضعیت: {server['last_status']}
💯 Health Score: {health.get('score', 0)}/100 ({health.get('grade', '?')})
🔗 اوت‌باندها: {outbound_count}"""

    if metric:
        text += f"""
💻 CPU: {metric['cpu_percent'] or '-'}%
🧠 RAM: {metric['ram_percent'] or '-'}%
⚡ Xray: {metric['xray_status'] or '-'}
⏱ Uptime: {metric['uptime'] or '-'}"""

    return text


def cmd_ping(args: list[str]) -> str:
    if not args:
        return "❓ استفاده: /ping <server_id>"

    try:
        server_id = int(args[0])
    except ValueError:
        return "❓ شناسه سرور باید عدد باشد."

    with connect() as conn:
        server = conn.execute("SELECT name FROM servers WHERE id=?", (server_id,)).fetchone()
        if not server:
            return "❌ سرور یافت نشد."

        outbounds = rows_to_dicts(conn.execute(
            "SELECT id, remark, last_status, last_ping_ms FROM outbounds WHERE server_id=? AND enabled=1 ORDER BY id LIMIT 15",
            (server_id,),
        ).fetchall())

    if not outbounds:
        return f"📭 سرور {server['name']} اوت‌باند فعالی ندارد."

    lines = [f"🏓 <b>پینگ {server['name']}:</b>\n"]
    for o in outbounds:
        icon = {"ok": "🟢", "high": "🟡", "timeout": "🔴", "error": "❌"}.get(o["last_status"], "⚪")
        ping = f"{o['last_ping_ms']}ms" if o["last_ping_ms"] else "-"
        lines.append(f"{icon} {o['remark']} — {ping}")

    return "\n".join(lines)


def cmd_alerts(args: list[str]) -> str:
    with connect() as conn:
        alerts = rows_to_dicts(conn.execute("""
            SELECT alerts.*, servers.name as server_name
            FROM alerts LEFT JOIN servers ON servers.id = alerts.server_id
            WHERE alerts.active = 1 ORDER BY alerts.created_at DESC LIMIT 10
        """).fetchall())

    if not alerts:
        return "✅ اعلان فعالی وجود ندارد."

    lines = ["⚠️ <b>اعلان‌های فعال:</b>\n"]
    for a in alerts:
        icon = "🔴" if a["severity"] == "critical" else "🟡"
        lines.append(f"{icon} {a['server_name'] or '-'}: {a['message'][:80]}")

    return "\n".join(lines)


def cmd_incidents(args: list[str]) -> str:
    with connect() as conn:
        incidents = rows_to_dicts(conn.execute("""
            SELECT incidents.*, servers.name as server_name
            FROM incidents LEFT JOIN servers ON servers.id = incidents.server_id
            WHERE incidents.status IN ('open', 'acknowledged')
            ORDER BY incidents.last_seen_at DESC LIMIT 10
        """).fetchall())

    if not incidents:
        return "✅ رخداد باز وجود ندارد."

    lines = ["🔴 <b>رخدادهای باز:</b>\n"]
    for i in incidents:
        icon = "🔴" if i["severity"] == "critical" else "🟡"
        status = {"open": "باز", "acknowledged": "تایید"}.get(i["status"], i["status"])
        lines.append(f"{icon} [{status}] {i['title'][:60]}")
        lines.append(f"   └ {i['server_name'] or '-'}")

    return "\n".join(lines)


def cmd_health(args: list[str]) -> str:
    with connect() as conn:
        servers = rows_to_dicts(conn.execute(
            "SELECT id, name FROM servers WHERE enabled=1 ORDER BY id LIMIT 15"
        ).fetchall())

    if not servers:
        return "📭 سرور فعالی وجود ندارد."

    lines = ["💯 <b>امتیاز سلامت:</b>\n"]
    for s in servers:
        health = calculate_health_score(s["id"])
        score = health.get("score", 0)
        grade = health.get("grade", "?")
        icon = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
        lines.append(f"{icon} {s['name']}: {score}/100 ({grade})")

    return "\n".join(lines)
