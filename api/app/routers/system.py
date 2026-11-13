"""
api/app/routers/system.py

FastAPI router for real-time hardware telemetry and JARVIS quick action triggers.

Endpoints:
  GET  /system/telemetry   -> Returns live CPU, RAM, GPU, Battery, Uptime and sub-agent statuses
  POST /system/quick-action -> One-click execution of high-priority routines (JARVIS activate, media, etc.)
"""

import asyncio
from typing import Any
from fastapi import APIRouter, HTTPException, Request, status

from api.app.schemas.system import (
    AgentTelemetryInfo,
    QuickActionRequest,
    QuickActionResponse,
    SystemTelemetryResponse,
)
from core.agent.schemas import ToolCall
from core.logging import get_logger
from tools.system.system_tools import (
    get_battery_status,
    get_cpu_usage,
    get_gpu_status,
    get_ram_usage,
    get_system_info,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["System & Telemetry"])

ACTIVE_AGENTS = [
    AgentTelemetryInfo(
        id="supervisor",
        name="NyxSupervisor",
        status="active",
        role="Multi-agent swarm coordinator and task planner",
    ),
    AgentTelemetryInfo(
        id="routine_agent",
        name="RoutineAgent",
        status="ready",
        role="Composite morning briefings, health audits, and master routines",
    ),
    AgentTelemetryInfo(
        id="system_agent",
        name="SystemAgent",
        status="ready",
        role="Real-time hardware sensors, CPU, RAM, thermals and processes",
    ),
    AgentTelemetryInfo(
        id="media_agent",
        name="MediaAgent",
        status="ready",
        role="YouTube playback and desktop MPRIS media player controls",
    ),
    AgentTelemetryInfo(
        id="terminal_agent",
        name="TerminalAgent",
        status="ready",
        role="Sandboxed Linux shell execution and development commands",
    ),
    AgentTelemetryInfo(
        id="comms_agent",
        name="CommsAgent",
        status="ready",
        role="Unified email inbox, Telegram alerts, and Discord channels",
    ),
    AgentTelemetryInfo(
        id="research_agent",
        name="ResearchAgent",
        status="ready",
        role="Web research, DuckDuckGo knowledge search, and page summarization",
    ),
    AgentTelemetryInfo(
        id="proactive_agent",
        name="ProactiveAgent",
        status="active",
        role="Autonomous sentinel: system health guardian, reminder dispatcher, and scheduled proactive alerts",
    ),
]


@router.get(
    "/telemetry",
    response_model=SystemTelemetryResponse,
    summary="Get real-time system hardware metrics and agent swarm telemetry",
)
async def get_telemetry() -> SystemTelemetryResponse:
    """Fetch live hardware telemetry (CPU, RAM, GPU, Battery) and sub-agent statuses."""
    loop = asyncio.get_running_loop()

    # Run system tools in thread pool to prevent blocking event loop
    cpu_res, ram_res, battery_res, gpu_res, sys_res = await asyncio.gather(
        loop.run_in_executor(None, get_cpu_usage),
        loop.run_in_executor(None, get_ram_usage),
        loop.run_in_executor(None, get_battery_status),
        loop.run_in_executor(None, get_gpu_status),
        loop.run_in_executor(None, get_system_info),
    )

    uptime = str(sys_res.data.get("uptime", "Unknown")) if sys_res.success else "Unknown"

    return SystemTelemetryResponse(
        cpu=cpu_res.data or {"percent": 0.0, "core_count": 1},
        ram=ram_res.data or {"used_gb": 0.0, "total_gb": 0.0, "percent": 0.0},
        battery=battery_res.data or {"percent": 100.0, "plugged_in": True, "status": "Full"},
        gpu=gpu_res.data or {"name": "Integrated / None", "available": False},
        uptime=uptime,
        agents=ACTIVE_AGENTS,
    )


@router.post(
    "/quick-action",
    response_model=QuickActionResponse,
    summary="Execute a one-click JARVIS quick action",
)
async def execute_quick_action(request: Request, body: QuickActionRequest) -> QuickActionResponse:
    """Trigger a fast-path action (e.g. activate all tasks, play media, or run diagnostic)."""
    tool_registry = getattr(request.app.state, "tool_registry", None)
    if not tool_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tool registry is not available on server state.",
        )

    action = body.action.strip().lower()
    params = body.params or {}

    tool_name = ""
    tool_args: dict[str, Any] = {}

    if action in ("activate_all_tasks", "activate_tasks", "jarvis_routine"):
        tool_name = "activate_all_tasks"
        tool_args = {}
    elif action in ("play_youtube", "play_lofi", "music"):
        tool_name = "play_youtube"
        tool_args = {"query": params.get("query", "lofi hip hop radio beats to relax/study to")}
    elif action in ("control_media", "media_control"):
        tool_name = "control_media"
        tool_args = {"action": params.get("action", "play_pause")}
    elif action in ("run_terminal", "terminal", "execute_terminal_command"):
        tool_name = "execute_terminal_command"
        tool_args = {"command": params.get("command", "git status")}
    elif action in ("check_emails", "emails"):
        tool_name = "check_emails"
        tool_args = {}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported quick action '{action}'.",
        )

    logger.info("quick_action_triggered", action=action, tool=tool_name, args=tool_args)

    call = ToolCall(name=tool_name, arguments=tool_args)
    result = await tool_registry.dispatch(call, confirmed=True)

    return QuickActionResponse(
        success=result.success,
        action=action,
        message=result.display_text or ("Action executed successfully." if result.success else "Action failed."),
        data=result.data or {},
    )


@router.get(
    "/proactive/status",
    summary="Get autonomous ProactiveSentinel health and operational status",
)
async def get_proactive_status(request: Request) -> dict[str, Any]:
    """Retrieve sentinel monitoring state, poll interval, and active alerts."""
    sentinel = getattr(request.app.state, "proactive_sentinel", None)
    if not sentinel:
        return {"status": "disabled", "message": "ProactiveSentinel is not running."}

    return {
        "status": "active",
        "poll_interval": sentinel.poll_interval,
        "warned_low_battery": sentinel._warned_low_battery,
        "warned_critical_battery": sentinel._warned_critical_battery,
        "subscribers_count": len(sentinel._subscribers),
    }


@router.post(
    "/proactive/sweep",
    summary="Trigger an immediate on-demand sweep of all proactive sentinel checks",
)
async def trigger_proactive_sweep(request: Request) -> dict[str, Any]:
    """Force an audit sweep for due reminders, battery limits, and thermal loads."""
    sentinel = getattr(request.app.state, "proactive_sentinel", None)
    if not sentinel:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ProactiveSentinel is not available.",
        )

    audit_result = await sentinel.run_single_audit()
    return {"status": "ok", "audit": audit_result}


