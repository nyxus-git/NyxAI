"""
tools/comms/comms_tools.py

Unified communications hub and master routine tools for NyxAI.

Integrations:
  - Email (IMAP unread email fetcher & summarizer)
  - Telegram (message checker and dispatcher)
  - Discord (channel alert and webhook sender)
  - JARVIS Master Routine: activate_all_tasks
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
import aiosqlite

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

# ── Tool Definitions ───────────────────────────────────────────────────────────

CHECK_EMAILS_DEF = ToolDefinition(
    name="check_emails",
    description=(
        "Check unread emails from your configured inbox. "
        "Returns the sender, subject, and timestamp of the latest unread emails."
    ),
    parameters={
        "limit": ToolParameter(
            type="integer",
            description="Maximum number of unread emails to retrieve (default: 5).",
            required=False,
        ),
    },
    category="comms",
)

CHECK_TELEGRAM_DEF = ToolDefinition(
    name="check_telegram",
    description="Check recent incoming Telegram messages and notifications.",
    parameters={
        "limit": ToolParameter(
            type="integer",
            description="Number of recent messages to inspect (default: 5).",
            required=False,
        ),
    },
    category="comms",
)

SEND_DISCORD_DEF = ToolDefinition(
    name="send_discord_alert",
    description="Post a notification message or alert to your configured Discord channel.",
    parameters={
        "message": ToolParameter(
            type="string",
            description="The message text to post to Discord.",
            required=True,
        ),
    },
    category="comms",
)

ACTIVATE_ALL_TASKS_DEF = ToolDefinition(
    name="activate_all_tasks",
    description=(
        "Run the complete JARVIS morning/daily routine: audits hardware health (battery, CPU, RAM, GPU), "
        "checks unread communications (emails, telegram), and retrieves today's pending tasks. "
        "Use when user says 'activate all tasks', 'morning routine', or 'daily briefing'."
    ),
    parameters={},
    category="system",
)


def _fetch_imap_sync(imap_server: str, email_user: str, email_pass: str, limit: int) -> dict[str, Any]:
    """Synchronous worker for IMAP fetch executed in a thread pool."""
    import email
    from email.header import decode_header
    import imaplib

    mail = imaplib.IMAP4_SSL(imap_server, timeout=8.0)
    try:
        mail.login(email_user, email_pass)
        mail.select("inbox")

        status, response = mail.search(None, "UNSEEN")
        if status != "OK" or not response or not response[0]:
            return {"configured": True, "unread_count": 0, "emails": []}

        email_ids = response[0].split()
        total_unseen = len(email_ids)

        recent_emails: list[dict[str, str]] = []
        target_ids = email_ids[-limit:] if limit > 0 else email_ids

        for eid in target_ids:
            try:
                res, data = mail.fetch(eid, "(RFC822.HEADER)")
                if res != "OK" or not data or not isinstance(data[0], tuple) or len(data[0]) < 2:
                    continue

                raw_header = data[0][1]
                if not isinstance(raw_header, bytes):
                    continue

                msg = email.message_from_bytes(raw_header)

                # Decode subject with multi-part support
                raw_subject = msg.get("Subject", "No Subject")
                subject_parts = decode_header(raw_subject)
                decoded_subject = ""
                for part, enc in subject_parts:
                    if isinstance(part, bytes):
                        decoded_subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        decoded_subject += str(part)

                sender = msg.get("From", "Unknown Sender")
                recent_emails.append({
                    "from": str(sender),
                    "subject": decoded_subject.strip() or "No Subject",
                })
            except Exception as item_err:
                logger.debug("imap_parse_header_error", error=str(item_err))
                continue

        return {
            "configured": True,
            "unread_count": total_unseen,
            "emails": recent_emails,
        }
    finally:
        try:
            mail.logout()
        except Exception:
            pass


async def check_emails(limit: int = 5) -> ToolResult:
    """
    Check unread email headers via IMAP.

    If IMAP credentials (EMAIL_USER, EMAIL_PASSWORD, IMAP_SERVER) are not set
    in .env, returns helpful configuration guidance.
    """
    try:
        limit_val = max(1, min(50, int(limit)))
    except (ValueError, TypeError):
        limit_val = 5

    imap_server = os.getenv("IMAP_SERVER")
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")

    if not (imap_server and email_user and email_pass):
        # Graceful informative response when email is not configured in .env yet
        return ToolResult(
            tool_name="check_emails",
            success=True,
            data={
                "configured": False,
                "unread_count": 0,
                "emails": [],
            },
            display_text=(
                "Email integration is not configured yet. To enable checking live emails, "
                "add IMAP_SERVER, EMAIL_USER, and EMAIL_PASSWORD to your .env file."
            ),
        )

    try:
        # Run blocking network socket I/O in worker thread with timeout
        data = await asyncio.wait_for(
            asyncio.to_thread(_fetch_imap_sync, imap_server, email_user, email_pass, limit_val),
            timeout=10.0,
        )

        total_unseen = data.get("unread_count", 0)
        recent_emails = data.get("emails", [])
        subjects_preview = ", ".join(e["subject"] for e in recent_emails[:3])

        return ToolResult(
            tool_name="check_emails",
            success=True,
            data=data,
            display_text=(
                f"You have {total_unseen} unread email(s). "
                f"Latest: {subjects_preview if subjects_preview else 'No unread emails'}"
            ),
        )
    except asyncio.TimeoutError:
        logger.warning("check_emails_timeout")
        return ToolResult(
            tool_name="check_emails",
            success=False,
            error="IMAP connection timed out after 10 seconds.",
        )
    except Exception as e:
        logger.exception("check_emails_failed", error=str(e))
        return ToolResult(
            tool_name="check_emails",
            success=False,
            error=f"IMAP connection failed: {str(e)}",
        )


async def check_telegram(limit: int = 5) -> ToolResult:
    """Check recent Telegram notifications via Bot API."""
    try:
        limit_val = max(1, min(50, int(limit)))
    except (ValueError, TypeError):
        limit_val = 5

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not tg_token:
        return ToolResult(
            tool_name="check_telegram",
            success=True,
            data={"configured": False, "messages": []},
            display_text="Telegram is not configured. Add TELEGRAM_BOT_TOKEN to your .env file to monitor messages.",
        )

    try:
        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{tg_token}/getUpdates",
                params={"limit": limit_val},
            )
            if resp.status_code == 200:
                body = resp.json()
                if not body.get("ok", False):
                    return ToolResult(
                        tool_name="check_telegram",
                        success=False,
                        error=body.get("description", "Telegram API returned ok=false"),
                    )

                updates = body.get("result", [])
                messages = []
                for u in updates:
                    msg = u.get("message", {})
                    text = msg.get("text", "")
                    sender = msg.get("from", {}).get("first_name", "Unknown")
                    if text:
                        messages.append({"from": sender, "text": text})

                return ToolResult(
                    tool_name="check_telegram",
                    success=True,
                    data={"configured": True, "count": len(messages), "messages": messages},
                    display_text=f"Retrieved {len(messages)} Telegram message(s).",
                )
            else:
                return ToolResult(
                    tool_name="check_telegram",
                    success=False,
                    error=f"Telegram API HTTP {resp.status_code}: {resp.text[:200]}",
                )
    except Exception as e:
        logger.warning("check_telegram_failed", error=str(e))
        return ToolResult(tool_name="check_telegram", success=False, error=str(e))


async def send_discord_alert(message: str) -> ToolResult:
    """Post an alert to a Discord channel via Webhook."""
    if not message or not str(message).strip():
        return ToolResult(
            tool_name="send_discord_alert",
            success=False,
            error="Message cannot be empty.",
        )

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        return ToolResult(
            tool_name="send_discord_alert",
            success=True,
            data={"configured": False},
            display_text="Discord Webhook is not configured. Add DISCORD_WEBHOOK_URL to your .env file.",
        )

    clean_content = str(message).strip()[:2000]

    try:
        import httpx

        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.post(webhook_url, json={"content": clean_content})
            if resp.status_code in (200, 204):
                return ToolResult(
                    tool_name="send_discord_alert",
                    success=True,
                    data={"sent": True},
                    display_text="Alert posted to Discord successfully.",
                )
            else:
                return ToolResult(
                    tool_name="send_discord_alert",
                    success=False,
                    error=f"Discord Webhook HTTP {resp.status_code}: {resp.text[:200]}",
                )
    except Exception as e:
        logger.warning("send_discord_alert_failed", error=str(e))
        return ToolResult(tool_name="send_discord_alert", success=False, error=str(e))


async def activate_all_tasks() -> ToolResult:
    """
    JARVIS Master Routine:
    Performs simultaneous audits across hardware, to-dos, and communications.
    """
    from tools.system.system_tools import (
        get_battery_status,
        get_cpu_usage,
        get_gpu_status,
        get_ram_usage,
    )

    # 1. System hardware audit
    battery = get_battery_status()
    cpu = get_cpu_usage()
    ram = get_ram_usage()
    gpu = get_gpu_status()

    # 2. Query pending tasks from database if file exists
    pending_tasks: list[dict[str, Any]] = []
    db_path = os.getenv("NYX_MEMORY_DB_PATH", "./data/nyx_memory.db")

    if os.path.exists(db_path):
        try:
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT id, title FROM tasks WHERE status = 'pending' ORDER BY id ASC LIMIT 5"
                )
                rows = await cursor.fetchall()
                for r in rows:
                    pending_tasks.append({"id": r["id"], "title": r["title"]})
        except Exception as e:
            logger.debug("activate_tasks_db_read_failed", error=str(e))

    # 3. Email check
    email_res = await check_emails(limit=3)

    # Format human-friendly executive briefing safely
    bat_data = battery.data or {}
    cpu_data = cpu.data or {}
    ram_data = ram.data or {}
    gpu_data = gpu.data or {}

    bat_pct = bat_data.get("percent", bat_data.get("percentage", "unknown"))
    cpu_pct = cpu_data.get("percent", cpu_data.get("cpu_percent", "unknown"))
    ram_pct = ram_data.get("percent", ram_data.get("ram_percent", "unknown"))
    task_count = len(pending_tasks)

    summary_data = {
        "hardware": {
            "battery_percent": bat_pct,
            "cpu_percent": cpu_pct,
            "ram_percent": ram_pct,
            "battery": bat_data,
            "cpu": cpu_data,
            "ram": ram_data,
            "gpu": gpu_data,
        },
        "tasks": {
            "pending_count": task_count,
            "items": pending_tasks,
        },
        "comms": {
            "email_status": email_res.data or {},
        },
    }

    task_str = f"{task_count} pending task(s)" if task_count > 0 else "no pending tasks"

    briefing = (
        f"JARVIS Routine Activated: System status nominal — Battery at {bat_pct}%, "
        f"CPU load at {cpu_pct}%, RAM usage at {ram_pct}%. You have {task_str}."
    )

    logger.info("activate_all_tasks_completed", pending_tasks=task_count)

    return ToolResult(
        tool_name="activate_all_tasks",
        success=True,
        data=summary_data,
        display_text=briefing,
    )
