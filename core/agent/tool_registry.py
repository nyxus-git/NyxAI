"""
core/agent/tool_registry.py

Central tool registry for NyxAI's agent system.

The ToolRegistry is the single place where tools are registered and dispatched.
It:
  1. Holds a mapping of tool_name → (ToolDefinition, handler_function)
  2. Converts all registered tools to Ollama's expected format
  3. Dispatches tool calls from the LLM to the correct handler
  4. Checks safety policy before dispatching
  5. Validates arguments via CommandValidator before any execution

Usage:
    registry = ToolRegistry()
    registry.register(GET_BATTERY_DEF, get_battery_status)
    tools_for_ollama = registry.get_tools_for_ollama()
    result = await registry.dispatch(tool_call)

A pre-built DEFAULT_REGISTRY is available at module level with all
Phase 2 tools already registered.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Coroutine, cast

from core.agent.schemas import ToolCall, ToolDefinition, ToolResult
from core.logging import get_logger
from safety.command_validator import CommandValidator
from safety.permissions import PermissionLevel, can_auto_execute, is_allowed
from safety.policy import get_permission_level

logger = get_logger(__name__)

# Type alias for a synchronous or async tool handler
ToolHandler = Callable[..., ToolResult | Coroutine[Any, Any, ToolResult]]


class ToolNotFoundError(Exception):
    """Raised when a tool is dispatched but not found in the registry."""
    pass


class ToolPermissionError(Exception):
    """Raised when a tool call is rejected by the safety policy."""

    def __init__(self, tool_name: str, level: PermissionLevel) -> None:
        self.tool_name = tool_name
        self.level = level
        super().__init__(
            f"Tool '{tool_name}' has permission level {level.name} "
            f"and cannot be auto-executed."
        )


class ToolValidationError(Exception):
    """Raised when tool arguments fail safety validation."""
    pass


class ToolRegistry:
    """
    Registry of all tools available to the NyxAI agent.

    Tools are registered with their definition (for LLM consumption) and
    a handler function (for execution). The registry enforces safety policy
    and argument validation before any tool executes.

    Thread safety note:
      In Phase 2, tools are registered at startup and never modified
      during request handling. This is safe for concurrent requests.
    """

    def __init__(self) -> None:
        # tool_name → (ToolDefinition, handler_function)
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        self._validator = CommandValidator()

    def register(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        """
        Register a tool with its definition and handler.

        Args:
            definition: The ToolDefinition describing the tool to the LLM.
            handler: A callable that executes the tool. Must return ToolResult.
                     Called with keyword arguments matching the tool's parameters.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if definition.name in self._tools:
            raise ValueError(
                f"Tool '{definition.name}' is already registered. "
                f"Use a unique name for each tool."
            )

        self._tools[definition.name] = (definition, handler)
        logger.debug(
            "tool_registered",
            name=definition.name,
            category=definition.category,
            permission=get_permission_level(definition.name).name,
        )

    def get_tools_for_ollama(self) -> list[dict]:
        """
        Return all registered tools in Ollama's JSON format.

        This list is passed directly to Ollama's /api/chat endpoint
        as the 'tools' parameter.

        Returns:
            List of tool definition dicts in Ollama format.
        """
        return [
            definition.to_ollama_format()
            for definition, _ in self._tools.values()
        ]

    def get_tool_names(self) -> list[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Return True if a tool with the given name is registered."""
        return name in self._tools

    async def dispatch(self, tool_call: ToolCall) -> ToolResult:
        """
        Dispatch a tool call from the LLM: validate → check policy → execute.

        This is the safe execution path. It enforces:
        1. The tool exists in the registry
        2. The tool is not BLOCKED by the safety policy
        3. The tool is auto-executable (SAFE level) — CONFIRMATION+ is rejected in Phase 2
        4. The arguments pass CommandValidator checks

        Args:
            tool_call: The ToolCall from the LLM (name + arguments).

        Returns:
            ToolResult from the tool handler.

        Raises:
            ToolNotFoundError: If the tool name is not registered.
            ToolPermissionError: If the tool requires human confirmation.
            ToolValidationError: If arguments fail safety validation.
        """
        tool_name = tool_call.name

        # 1. Check registry
        if tool_name not in self._tools:
            logger.warning("tool_dispatch_not_found", tool_name=tool_name)
            raise ToolNotFoundError(
                f"Tool '{tool_name}' is not registered. "
                f"The LLM may have hallucinated a tool name."
            )

        # 2. Check safety policy
        permission = get_permission_level(tool_name)
        if not is_allowed(permission):
            logger.error("tool_dispatch_blocked", tool_name=tool_name)
            raise ToolPermissionError(tool_name, permission)

        # 3. In Phase 2 — only auto-execute SAFE tools
        #    CONFIRMATION tools return a pending result for the API client to approve
        if not can_auto_execute(permission):
            logger.info(
                "tool_dispatch_needs_confirmation",
                tool_name=tool_name,
                permission=permission.name,
            )
            # Return a special "pending confirmation" result
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=None,
                data={"status": "pending_confirmation", "arguments": tool_call.arguments},
                display_text=(
                    f"Tool '{tool_name}' requires your confirmation before executing. "
                    f"Arguments: {tool_call.arguments}"
                ),
            )

        # 4. Validate arguments
        validation = self._validator.validate_tool_args(tool_name, tool_call.arguments)
        if not validation.ok:
            logger.warning(
                "tool_dispatch_validation_failed",
                tool_name=tool_name,
                reason=validation.reason,
            )
            raise ToolValidationError(
                f"Tool '{tool_name}' argument validation failed: {validation.reason}"
            )

        # 5. Execute the tool
        _, handler = self._tools[tool_name]
        logger.info(
            "tool_dispatch_executing",
            tool_name=tool_name,
            arguments=tool_call.arguments,
        )

        try:
            if inspect.iscoroutinefunction(handler):
                raw_result = await handler(**tool_call.arguments)
            else:
                raw_result = handler(**tool_call.arguments)
            
            result = cast(ToolResult, raw_result)
            logger.info(
                "tool_dispatch_complete",
                tool_name=tool_name,
                success=result.success,
            )
            return result

        except TypeError as e:
            # Argument mismatch — LLM provided wrong argument names
            logger.error("tool_dispatch_arg_mismatch", tool_name=tool_name, error=str(e))
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' received invalid arguments: {str(e)}",
            )

        except Exception as e:
            logger.exception("tool_dispatch_runtime_error", tool_name=tool_name, error=str(e))
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' encountered an error: {str(e)}",
            )


# ─── Default Registry ─────────────────────────────────────────────────────────
# Pre-built registry with all Phase 2 tools registered.
# Import this in main.py and pass it to NyxAgent.


def build_default_registry() -> ToolRegistry:
    """
    Build and return the default tool registry with all Phase 2 tools.

    Called once at application startup in main.py lifespan.

    Returns:
        A ToolRegistry with all system, file, and browser tools registered.
    """
    from tools.browser.browser_tools import (
        OPEN_URL_DEF,
        WEB_SEARCH_DEF,
        READ_WEBPAGE_DEF,
        open_url,
        web_search,
        read_webpage,
    )
    from tools.files.file_tools import OPEN_APPLICATION_DEF, open_application
    from tools.files.fs_tools import (
        LIST_DIRECTORY_DEF,
        READ_FILE_DEF,
        list_directory,
        read_file,
    )
    from tools.system.system_tools import (
        GET_BATTERY_DEF,
        GET_CPU_DEF,
        GET_GPU_DEF,
        GET_RAM_DEF,
        GET_SYSINFO_DEF,
        GET_TIME_DEF,
        get_battery_status,
        get_cpu_usage,
        get_gpu_status,
        get_ram_usage,
        get_current_time,
        get_system_info,
    )
    from tools.tasks.task_tools import (
        ADD_TASK_DEF,
        LIST_TASKS_DEF,
        COMPLETE_TASK_DEF,
        add_task,
        list_tasks,
        complete_task,
    )

    registry = ToolRegistry()

    # ── System tools ──────────────────────────────────────────────────────────
    registry.register(GET_BATTERY_DEF, get_battery_status)
    registry.register(GET_CPU_DEF, get_cpu_usage)
    registry.register(GET_RAM_DEF, get_ram_usage)
    registry.register(GET_TIME_DEF, get_current_time)
    registry.register(GET_SYSINFO_DEF, get_system_info)
    registry.register(GET_GPU_DEF, get_gpu_status)

    # ── Application tools ─────────────────────────────────────────────────────
    registry.register(OPEN_APPLICATION_DEF, open_application)

    # ── File system tools ─────────────────────────────────────────────────────
    registry.register(LIST_DIRECTORY_DEF, list_directory)
    registry.register(READ_FILE_DEF, read_file)

    # ── Browser tools ─────────────────────────────────────────────────────────
    registry.register(OPEN_URL_DEF, open_url)
    registry.register(WEB_SEARCH_DEF, web_search)
    registry.register(READ_WEBPAGE_DEF, read_webpage)

    # ── Task tools ────────────────────────────────────────────────────────────
    registry.register(ADD_TASK_DEF, add_task)
    registry.register(LIST_TASKS_DEF, list_tasks)
    registry.register(COMPLETE_TASK_DEF, complete_task)

    logger.info(
        "tool_registry_built",
        tool_count=len(registry.get_tool_names()),
        tools=registry.get_tool_names(),
    )

    return registry
