"""
core/agent/proactive.py

Autonomous Proactive Sentinel and Event Hub for NyxAI.

Operates as a background intelligence monitor:
  1. Active Reminder & Alarm Dispatcher: Polls pending reminders, updates status,
     fires notify-send notifications, triggers audio alert chimes, and speaks alerts.
  2. Battery Health Guardian: Detects discharging below 15% and 8% critical thresholds,
     advising the user before system shutdown.
  3. CPU/Thermal Sentinel: Alerts on sustained high CPU (>95%) utilization.
  4. Real-time Event Hub: Asynchronous pub-sub broadcasting proactive events
     to WebSockets, Companion UI, and desktop daemons.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import shutil
import subprocess
from typing import Any, Awaitable, Callable
import aiosqlite

from core.logging import get_logger
from tools.system.system_tools import get_battery_status, get_cpu_usage
from voice.wakeword.chime import play_chime

logger = get_logger(__name__)


def send_desktop_notification(title: str, message: str) -> None:
    """Post native desktop notification via notify-send if available on system."""
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(["notify-send", "-a", "NyxAI", title, message[:250]])
        except Exception as e:
            logger.debug("proactive_notify_send_failed", error=str(e))


class ProactiveSentinel:
    """
    Autonomous background sentinel monitoring reminders, battery health,
    and system thermals, dispatching events to desktop and Companion UI.
    """

    def __init__(
        self,
        db_path: str = "./data/nyx_memory.db",
        poll_interval: float = 15.0,
        tts_speaker: Any = None,
    ) -> None:
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.tts_speaker = tts_speaker

        # Alert state tracking to avoid alert spamming
        self._warned_low_battery = False
        self._warned_critical_battery = False
        self._consecutive_high_cpu = 0

        # Event subscribers
        self._subscribers: set[Callable[[dict[str, Any]], Awaitable[None]]] = set()

    def subscribe(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register an async callback for proactive events."""
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Unregister an async event callback."""
        self._subscribers.discard(callback)

    async def emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event payload to all registered listeners."""
        payload = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        logger.info("proactive_event_emitted", event_type=event_type, data=data)
        for sub in list(self._subscribers):
            try:
                await sub(payload)
            except Exception as e:
                logger.warning("event_subscriber_failed", error=str(e))

    async def check_reminders(self) -> list[dict[str, Any]]:
        """Query due pending reminders, mark them completed, and dispatch alerts."""
        if not os.path.exists(self.db_path):
            return []

        now = datetime.now(timezone.utc).isoformat()
        triggered = []

        try:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT id, title, due_at FROM reminders WHERE status = 'pending' AND due_at <= ?",
                    (now,),
                )
                rows = await cursor.fetchall()
                for row in rows:
                    r_id = row["id"]
                    title = row["title"]
                    triggered.append({"id": r_id, "title": title})

                    # Mark completed
                    await conn.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (r_id,))
                    logger.info("proactive_reminder_fired", reminder_id=r_id, title=title)

                    # 1. Desktop Notification
                    send_desktop_notification("NyxAI Reminder", title)

                    # 2. Audio Chime
                    play_chime("warning", async_play=True)

                    # 3. Spoken Announcement (if TTS available)
                    if self.tts_speaker and hasattr(self.tts_speaker, "speak"):
                        try:
                            self.tts_speaker.speak(f"Reminder: {title}")
                        except Exception as err:
                            logger.debug("proactive_tts_failed", error=str(err))

                    # 4. Broadcast event
                    await self.emit_event("reminder_triggered", {"id": r_id, "title": title})

                if rows:
                    await conn.commit()
        except Exception as e:
            logger.error("check_reminders_failed", error=str(e))

        return triggered

    async def check_battery(self) -> dict[str, Any] | None:
        """Inspect battery levels and issue proactive warnings when discharging."""
        try:
            result = get_battery_status()
            if not result.success or not result.data:
                return None

            data = result.data
            percent = data.get("percent")
            plugged_in = data.get("plugged_in")

            if percent is None:
                return None

            # Reset flags if plugged in
            if plugged_in is True:
                self._warned_low_battery = False
                self._warned_critical_battery = False
                return None

            # Discharging checks
            if percent <= 8 and not self._warned_critical_battery:
                self._warned_critical_battery = True
                msg = f"Battery critical at {percent}%. Connect charger immediately."
                send_desktop_notification("NyxAI Battery Critical", msg)
                play_chime("warning", async_play=True)
                if self.tts_speaker and hasattr(self.tts_speaker, "speak"):
                    self.tts_speaker.speak(msg)
                await self.emit_event("battery_warning", {"percent": percent, "critical": True})
                return {"type": "critical", "percent": percent}

            elif percent <= 15 and not self._warned_low_battery:
                self._warned_low_battery = True
                msg = f"Battery is at {percent}%. Please connect AC adapter."
                send_desktop_notification("NyxAI Battery Low", msg)
                play_chime("warning", async_play=True)
                await self.emit_event("battery_warning", {"percent": percent, "critical": False})
                return {"type": "low", "percent": percent}

        except Exception as e:
            logger.debug("check_battery_failed", error=str(e))

        return None

    async def check_cpu_health(self) -> float | None:
        """Inspect CPU utilization and detect sustained high workloads."""
        try:
            result = get_cpu_usage()
            if not result.success or not result.data:
                return None

            cpu_percent = result.data.get("cpu_percent", 0.0)
            if cpu_percent >= 95.0:
                self._consecutive_high_cpu += 1
                if self._consecutive_high_cpu >= 2:
                    msg = f"High CPU utilization sustained at {cpu_percent}%."
                    send_desktop_notification("NyxAI Performance Alert", msg)
                    await self.emit_event("cpu_alert", {"cpu_percent": cpu_percent})
            else:
                self._consecutive_high_cpu = 0

            return cpu_percent
        except Exception as e:
            logger.debug("check_cpu_failed", error=str(e))
            return None

    async def run_single_audit(self) -> dict[str, Any]:
        """Execute a single sweep of all proactive checks."""
        reminders = await self.check_reminders()
        battery = await self.check_battery()
        cpu = await self.check_cpu_health()
        return {
            "reminders_fired": len(reminders),
            "battery_alert": battery is not None,
            "cpu_percent": cpu,
        }

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        """Continuous background execution loop."""
        logger.info("proactive_sentinel_started", interval=self.poll_interval)
        while True:
            if stop_event and stop_event.is_set():
                break

            try:
                await self.run_single_audit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("proactive_sentinel_sweep_error", error=str(e))

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

        logger.info("proactive_sentinel_stopped")

