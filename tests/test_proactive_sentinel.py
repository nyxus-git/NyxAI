"""
tests/test_proactive_sentinel.py

Unit tests for ProactiveSentinel autonomous background intelligence monitor,
active reminder dispatcher, battery health guardian, and event pub-sub hub.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import aiosqlite
import pytest

from core.agent.proactive import ProactiveSentinel, send_desktop_notification
from core.agent.schemas import ToolResult


@pytest.fixture
async def temp_db_path(tmp_path: Path) -> str:
    """Create a temporary SQLite database with the reminders table schema."""
    db_file = tmp_path / "test_nyx_memory.db"
    async with aiosqlite.connect(str(db_file)) as conn:
        await conn.execute(
            """
            CREATE TABLE reminders (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            """
        )
        await conn.commit()
    return str(db_file)


class TestProactiveSentinel:
    """Tests for ProactiveSentinel background intelligence and events."""

    def test_sentinel_initialization(self) -> None:
        sentinel = ProactiveSentinel(db_path="/tmp/fake.db", poll_interval=10.0)
        assert sentinel.db_path == "/tmp/fake.db"
        assert sentinel.poll_interval == 10.0
        assert sentinel._warned_low_battery is False

    @pytest.mark.asyncio
    async def test_event_subscription_and_broadcast(self) -> None:
        sentinel = ProactiveSentinel()
        received_events = []

        async def listener(event: dict) -> None:
            received_events.append(event)

        sentinel.subscribe(listener)
        await sentinel.emit_event("test_alert", {"level": "info", "msg": "hello"})

        assert len(received_events) == 1
        assert received_events[0]["type"] == "test_alert"
        assert received_events[0]["data"]["msg"] == "hello"

        sentinel.unsubscribe(listener)
        await sentinel.emit_event("test_alert_2", {"msg": "should not receive"})
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_check_reminders_triggers_due_and_marks_completed(
        self, temp_db_path: str
    ) -> None:
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute(
                "INSERT INTO reminders (id, title, due_at, status) VALUES (?, ?, ?, ?)",
                ("rem-1", "Review architecture design", past_time, "pending"),
            )
            await conn.execute(
                "INSERT INTO reminders (id, title, due_at, status) VALUES (?, ?, ?, ?)",
                ("rem-2", "Submit weekly report", future_time, "pending"),
            )
            await conn.commit()

        mock_speaker = MagicMock()
        sentinel = ProactiveSentinel(db_path=temp_db_path, tts_speaker=mock_speaker)

        with patch("core.agent.proactive.send_desktop_notification") as mock_notify, \
             patch("core.agent.proactive.play_chime") as mock_chime:
            fired = await sentinel.check_reminders()

            assert len(fired) == 1
            assert fired[0]["id"] == "rem-1"
            assert fired[0]["title"] == "Review architecture design"

            assert mock_notify.called
            assert mock_chime.called
            assert mock_speaker.speak.called

        # Verify database updated status to 'completed'
        async with aiosqlite.connect(temp_db_path) as conn:
            cursor = await conn.execute("SELECT id, status FROM reminders WHERE id = 'rem-1'")
            row = await cursor.fetchone()
            assert row[1] == "completed"

            # Future reminder remains pending
            cursor2 = await conn.execute("SELECT id, status FROM reminders WHERE id = 'rem-2'")
            row2 = await cursor2.fetchone()
            assert row2[1] == "pending"

    @pytest.mark.asyncio
    async def test_battery_guardian_low_and_critical_detection(self) -> None:
        sentinel = ProactiveSentinel()

        # 1. Battery at 12%, discharging -> triggers low battery warning
        mock_low_result = ToolResult(
            tool_name="get_battery_status",
            success=True,
            data={"percent": 12.0, "plugged_in": False, "status": "Discharging"},
        )
        with patch("core.agent.proactive.get_battery_status", return_value=mock_low_result), \
             patch("core.agent.proactive.send_desktop_notification") as mock_notify, \
             patch("core.agent.proactive.play_chime") as mock_chime:
            res = await sentinel.check_battery()
            assert res is not None
            assert res["type"] == "low"
            assert res["percent"] == 12.0
            assert mock_notify.called
            assert mock_chime.called
            assert sentinel._warned_low_battery is True

        # Second check at same level does not spam alert
        with patch("core.agent.proactive.get_battery_status", return_value=mock_low_result):
            res2 = await sentinel.check_battery()
            assert res2 is None

        # 2. Battery drops to 6%, discharging -> triggers critical alert
        mock_critical_result = ToolResult(
            tool_name="get_battery_status",
            success=True,
            data={"percent": 6.0, "plugged_in": False, "status": "Discharging"},
        )
        with patch("core.agent.proactive.get_battery_status", return_value=mock_critical_result), \
             patch("core.agent.proactive.send_desktop_notification") as mock_notify:
            res_crit = await sentinel.check_battery()
            assert res_crit is not None
            assert res_crit["type"] == "critical"
            assert sentinel._warned_critical_battery is True

        # 3. User plugs in AC adapter -> resets alert flags
        mock_plugged_result = ToolResult(
            tool_name="get_battery_status",
            success=True,
            data={"percent": 7.0, "plugged_in": True, "status": "Charging"},
        )
        with patch("core.agent.proactive.get_battery_status", return_value=mock_plugged_result):
            res_plugged = await sentinel.check_battery()
            assert res_plugged is None
            assert sentinel._warned_low_battery is False
            assert sentinel._warned_critical_battery is False

    @pytest.mark.asyncio
    async def test_cpu_sentinel_sustained_load_detection(self) -> None:
        sentinel = ProactiveSentinel()

        mock_high_cpu = ToolResult(
            tool_name="get_cpu_usage",
            success=True,
            data={"cpu_percent": 97.5, "core_count": 16},
        )

        with patch("core.agent.proactive.get_cpu_usage", return_value=mock_high_cpu), \
             patch("core.agent.proactive.send_desktop_notification") as mock_notify:
            # Check 1: registers count = 1
            cpu1 = await sentinel.check_cpu_health()
            assert cpu1 == 97.5
            assert not mock_notify.called

            # Check 2: sustained load >= 2 -> fires notification
            cpu2 = await sentinel.check_cpu_health()
            assert cpu2 == 97.5
            assert mock_notify.called

    @pytest.mark.asyncio
    async def test_run_single_audit(self, temp_db_path: str) -> None:
        sentinel = ProactiveSentinel(db_path=temp_db_path)
        with patch.object(sentinel, "check_reminders", return_value=[{"id": "1"}]), \
             patch.object(sentinel, "check_battery", return_value=None), \
             patch.object(sentinel, "check_cpu_health", return_value=12.5):
            audit = await sentinel.run_single_audit()
            assert audit["reminders_fired"] == 1
            assert audit["battery_alert"] is False
            assert audit["cpu_percent"] == 12.5

    @pytest.mark.asyncio
    async def test_run_loop_stop_event(self) -> None:
        sentinel = ProactiveSentinel(poll_interval=0.01)
        stop_event = asyncio.Event()
        stop_event.set()

        # Should return immediately because stop_event is set
        await sentinel.run_loop(stop_event=stop_event)
        assert stop_event.is_set()

    def test_send_desktop_notification_invokes_popen(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/notify-send"), \
             patch("subprocess.Popen") as mock_popen:
            send_desktop_notification("Test Alert", "Message content")
            assert mock_popen.called
            args = mock_popen.call_args[0][0]
            assert "notify-send" in args
            assert "Test Alert" in args

