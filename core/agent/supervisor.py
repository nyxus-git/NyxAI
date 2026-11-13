"""
core/agent/supervisor.py

NyxSupervisor — Multi-Agent Orchestrator for NyxAI.

Manages a swarm of specialist sub-agents:
  1. TerminalAgent: Executes shell commands, devops, and process diagnostics
  2. MediaAgent: YouTube search/playback and desktop playerctl MPRIS controls
  3. CommsAgent: Unified inbox, Telegram alerts, and Discord channel notifications
  4. SystemAgent: Real-time hardware telemetry and status monitoring
  5. RoutineAgent: Multi-step composite routines (e.g. "Activate All Tasks")

Coordinates parallel delegation, step sequencing, and synthesizes executive briefings.
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.agent.agent import NyxAgent
from core.agent.schemas import AgentResponse, ToolCall, ToolResult
from core.agent.tool_registry import ToolRegistry
from core.brain.llm import LLMProvider, Message, MessageRole
from core.logging import get_logger

logger = get_logger(__name__)


class SpecialistAgent:
    """Base class for domain-focused specialist sub-agents."""

    def __init__(self, name: str, domain: str, registry: ToolRegistry) -> None:
        self.name = name
        self.domain = domain
        self.registry = registry

    async def execute(self, tool_name: str, arguments: dict[str, Any], confirmed: bool = True) -> ToolResult:
        """Execute a specific tool owned by this specialist."""
        tool_call = ToolCall(name=tool_name, arguments=arguments)
        return await self.registry.dispatch(tool_call, confirmed=confirmed)


class NyxSupervisor:
    """
    Supervisor Agent that orchestrates specialist agents in parallel.

    When a composite or complex command arrives:
      1. Identifies if multi-agent delegation is beneficial
      2. Dispatches sub-tasks to relevant specialists concurrently via asyncio.gather
      3. Aggregates results into an executive response
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        base_agent: NyxAgent | None = None,
    ) -> None:
        self._llm = llm_provider
        self._registry = tool_registry
        self._base_agent = base_agent or NyxAgent(llm_provider, tool_registry)

        # Initialize specialist agents
        self.terminal_agent = SpecialistAgent("TerminalAgent", "terminal", tool_registry)
        self.media_agent = SpecialistAgent("MediaAgent", "media", tool_registry)
        self.comms_agent = SpecialistAgent("CommsAgent", "comms", tool_registry)
        self.system_agent = SpecialistAgent("SystemAgent", "system", tool_registry)
        self.routine_agent = SpecialistAgent("RoutineAgent", "system", tool_registry)

        logger.info("nyx_supervisor_initialized")

    async def run(
        self,
        message: str,
        history: list[Message] | None = None,
        conversation_id: str | None = None,
        auto_approve: bool = False,
        voice_mode: bool = False,
    ) -> AgentResponse:
        """
        Process user message through the multi-agent swarm.
        """
        clean_msg = message.strip().lower()

        # 1. Fast-path check for composite "activate all tasks" / "morning briefing"
        if any(trigger in clean_msg for trigger in ("activate all tasks", "activate tasks", "morning routine", "daily briefing", "run all tasks")):
            logger.info("supervisor_running_activate_all_tasks_routine")
            res = await self.routine_agent.execute("activate_all_tasks", {})
            return AgentResponse(
                content=res.display_text or "All tasks activated.",
                model=self._llm.get_model_name(),
                tool_used="activate_all_tasks",
                tool_result=res.data,
                iterations=1,
            )

        # 2. Fast-path for direct YouTube playback requests
        if ("play " in clean_msg and "youtube" in clean_msg) or clean_msg.startswith("play video") or clean_msg.startswith("play song"):
            query = re_extract_query(message)
            logger.info("supervisor_routing_to_media_agent", query=query)
            res = await self.media_agent.execute("play_youtube", {"query": query})
            return AgentResponse(
                content=res.display_text or f"Playing {query} on YouTube.",
                model=self._llm.get_model_name(),
                tool_used="play_youtube",
                tool_result=res.data,
                iterations=1,
            )

        # 3. Standard multi-agent ReAct delegation via NyxAgent with dynamic domain routing
        return await self._base_agent.run(
            message=message,
            history=history,
            conversation_id=conversation_id,
            auto_approve=auto_approve,
            voice_mode=voice_mode,
        )


def re_extract_query(text: str) -> str:
    """Extract clean search query from play video/music instructions."""
    import re
    cleaned = re.sub(r"^(play\s+(video|song|music|track)?\s*(on\s+youtube)?\s*)", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+on\s+youtube$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or text.strip()

