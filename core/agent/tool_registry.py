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

A pre-built registry is available via build_default_registry() with all
built-in tools registered.
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


# Tool Name Aliases for LLM hallucination and naming drift mitigation
TOOL_NAME_ALIASES: dict[str, str] = {
    # System tools
    "get_battery": "get_battery_status",
    "battery": "get_battery_status",
    "battery_status": "get_battery_status",
    "check_battery": "get_battery_status",
    "get_cpu": "get_cpu_usage",
    "cpu": "get_cpu_usage",
    "cpu_usage": "get_cpu_usage",
    "check_cpu": "get_cpu_usage",
    "get_ram": "get_ram_usage",
    "ram": "get_ram_usage",
    "ram_usage": "get_ram_usage",
    "memory": "get_ram_usage",
    "get_time": "get_current_time",
    "time": "get_current_time",
    "current_time": "get_current_time",
    "clock": "get_current_time",
    "system_info": "get_system_info",
    "sysinfo": "get_system_info",
    "get_gpu": "get_gpu_status",
    "gpu": "get_gpu_status",
    "gpu_status": "get_gpu_status",
    # Applications
    "open_app": "open_application",
    "launch_app": "open_application",
    "launch_application": "open_application",
    "run_app": "open_application",
    "start_app": "open_application",
    "open_program": "open_application",
    # Browser
    "search_web": "web_search",
    "google": "web_search",
    "duckduckgo": "web_search",
    "search": "web_search",
    "open_website": "open_url",
    "open_browser": "open_url",
    "browse": "open_url",
    "read_url": "read_webpage",
    "read_page": "read_webpage",
    "scrape_page": "read_webpage",
    # Files
    "read": "read_file",
    "cat": "read_file",
    "view_file": "read_file",
    "list_dir": "list_directory",
    "dir": "list_directory",
    "ls": "list_directory",
    "find_files": "search_files",
    "find_file": "search_files",
    "search_file": "search_files",
    # Tasks
    "create_task": "add_task",
    "new_task": "add_task",
    "set_task": "add_task",
    "get_tasks": "list_tasks",
    "show_tasks": "list_tasks",
    "todos": "list_tasks",
    "done_task": "complete_task",
    "finish_task": "complete_task",
    "remind_me": "set_reminder",
    "add_reminder": "set_reminder",
    # Planning
    "make_plan": "create_plan",
    "plan": "create_plan",
    # Terminal
    "run_command": "execute_terminal_command",
    "exec_command": "execute_terminal_command",
    "shell_command": "execute_terminal_command",
    "terminal": "execute_terminal_command",
    # Media & YouTube
    "youtube": "play_youtube",
    "play_video": "play_youtube",
    "play_song": "play_youtube",
    "play_music": "play_youtube",
    "media": "control_media",
    # Communications
    "email": "check_emails",
    "emails": "check_emails",
    "get_emails": "check_emails",
    "read_emails": "check_emails",
    "telegram": "check_telegram",
    "get_telegram": "check_telegram",
    "discord": "send_discord_alert",
    "post_discord": "send_discord_alert",
    # JARVIS Master Routine
    "activate_tasks": "activate_all_tasks",
    "morning_routine": "activate_all_tasks",
    "daily_briefing": "activate_all_tasks",
}

# Parameter Aliases per tool
PARAM_ALIASES: dict[str, dict[str, str]] = {
    "execute_terminal_command": {
        "cmd": "command",
        "shell_command": "command",
    },
    "play_youtube": {
        "song": "query",
        "video": "query",
        "search": "query",
        "title": "query",
    },
    "send_discord_alert": {
        "text": "message",
        "alert": "message",
        "content": "message",
    },
    "open_application": {
        "app": "application",
        "app_name": "application",
        "name": "application",
        "program": "application",
        "app_title": "application",
    },
    "web_search": {
        "search_query": "query",
        "q": "query",
        "term": "query",
        "text": "query",
        "search_term": "query",
    },
    "open_url": {
        "link": "url",
        "uri": "url",
        "address": "url",
        "website": "url",
        "site": "url",
    },
    "read_webpage": {
        "link": "url",
        "uri": "url",
        "address": "url",
        "website": "url",
        "site": "url",
    },
    "read_file": {
        "file_path": "path",
        "filepath": "path",
        "filename": "path",
        "file": "path",
    },
    "list_directory": {
        "directory": "path",
        "dir": "path",
        "folder": "path",
        "dir_path": "path",
    },
    "search_files": {
        "query": "pattern",
        "name": "pattern",
        "file_pattern": "pattern",
        "dir": "path",
        "directory": "path",
        "folder": "path",
    },
    "add_task": {
        "task": "title",
        "text": "title",
        "description": "title",
        "name": "title",
        "task_title": "title",
    },
    "complete_task": {
        "id": "task_id",
        "task": "task_id",
    },
    "set_reminder": {
        "text": "message",
        "reminder": "message",
        "msg": "message",
        "timestamp": "remind_at",
        "datetime": "remind_at",
        "date": "remind_at",
        "time": "remind_at",
    },
    "create_plan": {
        "goal": "task",
        "objective": "task",
        "description": "task",
    },
}


class ToolRegistry:
    """
    Registry of all tools available to the NyxAI agent.

    Tools are registered with their definition (for LLM consumption) and
    a handler function (for execution). The registry enforces safety policy,
    alias normalization, and argument validation before any tool executes.

    Thread safety note:
      Tools are registered at startup and never modified during request
      handling. This is safe for concurrent requests.
    """

    def __init__(self) -> None:
        # tool_name → (ToolDefinition, handler_function)
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        # category → list of tool names
        self._by_category: dict[str, list[str]] = {}
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
        cat = definition.category or "general"
        if cat not in self._by_category:
            self._by_category[cat] = []
        self._by_category[cat].append(definition.name)

        logger.debug(
            "tool_registered",
            name=definition.name,
            category=definition.category,
            permission=get_permission_level(definition.name).name,
        )

    def get_categories(self) -> list[str]:
        """Return all distinct tool categories registered."""
        return sorted(list(self._by_category.keys()))

    def get_tools_by_category(self, category: str) -> list[ToolDefinition]:
        """Return all tool definitions belonging to a specific category."""
        names = self._by_category.get(category, [])
        return [self._tools[n][0] for n in names if n in self._tools]

    def get_tools_for_ollama(
        self,
        categories: list[str] | set[str] | None = None,
    ) -> list[dict]:
        """
        Return registered tools in Ollama's JSON format.

        Args:
            categories: Optional list of domain categories to filter by.
                        If None, all registered tools are returned.

        Returns:
            List of tool definition dicts in Ollama format.
        """
        if categories is None:
            return [
                definition.to_ollama_format()
                for definition, _ in self._tools.values()
            ]

        target_cats = set(categories)
        filtered = [
            definition.to_ollama_format()
            for definition, _ in self._tools.values()
            if definition.category in target_cats or definition.category == "general"
        ]
        # If filtering returned empty (e.g. invalid category), fall back to all tools
        return filtered if filtered else [
            definition.to_ollama_format()
            for definition, _ in self._tools.values()
        ]

    def get_tool_names(self) -> list[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Return True if a tool with the given name (or recognized alias) is registered."""
        canonical = TOOL_NAME_ALIASES.get(name.lower(), name)
        return canonical in self._tools

    def normalize_tool_call(self, tool_call: ToolCall) -> ToolCall:
        """
        Normalize tool name and parameter aliases to mitigate LLM hallucination.

        Args:
            tool_call: The raw tool call from the LLM.

        Returns:
            Normalized ToolCall with canonical tool name and argument keys.
        """
        # 1. Resolve tool name alias
        raw_name = tool_call.name.strip()
        canonical_name = TOOL_NAME_ALIASES.get(raw_name.lower(), raw_name)

        # 2. Resolve parameter aliases
        normalized_args: dict[str, Any] = {}
        tool_param_map = PARAM_ALIASES.get(canonical_name, {})

        for key, val in tool_call.arguments.items():
            clean_key = tool_param_map.get(key, key)
            normalized_args[clean_key] = val

        return ToolCall(name=canonical_name, arguments=normalized_args)

    async def dispatch(self, tool_call: ToolCall, confirmed: bool = False) -> ToolResult:
        """
        Dispatch a tool call from the LLM: normalize → validate → check policy → execute.

        This is the safe execution path. It enforces:
        1. Tool name and argument normalization
        2. The tool exists in the registry
        3. The tool is not BLOCKED by the safety policy
        4. The tool is auto-executable (SAFE level) unless confirmed=True for CONFIRMATION tools
        5. The arguments pass CommandValidator checks

        Args:
            tool_call: The ToolCall from the LLM (name + arguments).
            confirmed: Whether the user approved executing CONFIRMATION-level tools.

        Returns:
            ToolResult from the tool handler.

        Raises:
            ToolNotFoundError: If the tool name is not registered.
            ToolPermissionError: If the tool is BLOCKED.
            ToolValidationError: If arguments fail safety validation.
        """
        # 0. Normalize tool call name and argument aliases
        tool_call = self.normalize_tool_call(tool_call)
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

        # 3. Only auto-execute SAFE tools unless explicitly confirmed for CONFIRMATION tools
        if not can_auto_execute(permission) and not (
            confirmed and permission == PermissionLevel.CONFIRMATION
        ):
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


# Default Registry


def build_default_registry() -> ToolRegistry:
    """
    Build and return the default tool registry with all built-in tools.

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
        SEARCH_FILES_DEF,
        MOVE_FILE_DEF,
        COPY_FILE_DEF,
        DELETE_FILE_DEF,
        list_directory,
        read_file,
        search_files,
        move_file,
        copy_file,
        delete_file,
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
        SET_REMINDER_DEF,
        add_task,
        list_tasks,
        complete_task,
        set_reminder,
    )
    from tools.planning.planning_tools import (
        CREATE_PLAN_DEF,
        UPDATE_PLAN_DEF,
        create_plan,
        update_plan,
    )
    from tools.terminal.terminal_tools import (
        EXECUTE_TERMINAL_DEF,
        execute_terminal_command,
    )
    from tools.youtube.youtube_tools import (
        PLAY_YOUTUBE_DEF,
        CONTROL_MEDIA_DEF,
        play_youtube,
        control_media,
    )
    from tools.comms.comms_tools import (
        CHECK_EMAILS_DEF,
        CHECK_TELEGRAM_DEF,
        SEND_DISCORD_DEF,
        ACTIVATE_ALL_TASKS_DEF,
        check_emails,
        check_telegram,
        send_discord_alert,
        activate_all_tasks,
    )

    registry = ToolRegistry()

    # ── System tools
    registry.register(GET_BATTERY_DEF, get_battery_status)
    registry.register(GET_CPU_DEF, get_cpu_usage)
    registry.register(GET_RAM_DEF, get_ram_usage)
    registry.register(GET_TIME_DEF, get_current_time)
    registry.register(GET_SYSINFO_DEF, get_system_info)
    registry.register(GET_GPU_DEF, get_gpu_status)
    registry.register(ACTIVATE_ALL_TASKS_DEF, activate_all_tasks)

    # ── Application tools
    registry.register(OPEN_APPLICATION_DEF, open_application)

    # ── File system tools
    registry.register(LIST_DIRECTORY_DEF, list_directory)
    registry.register(READ_FILE_DEF, read_file)
    registry.register(SEARCH_FILES_DEF, search_files)
    registry.register(MOVE_FILE_DEF, move_file)
    registry.register(COPY_FILE_DEF, copy_file)
    registry.register(DELETE_FILE_DEF, delete_file)

    # ── Browser tools
    registry.register(OPEN_URL_DEF, open_url)
    registry.register(WEB_SEARCH_DEF, web_search)
    registry.register(READ_WEBPAGE_DEF, read_webpage)

    # ── Task tools
    registry.register(ADD_TASK_DEF, add_task)
    registry.register(LIST_TASKS_DEF, list_tasks)
    registry.register(COMPLETE_TASK_DEF, complete_task)
    registry.register(SET_REMINDER_DEF, set_reminder)

    # ── Planning tools
    registry.register(CREATE_PLAN_DEF, create_plan)
    registry.register(UPDATE_PLAN_DEF, update_plan)

    # ── Terminal tools
    registry.register(EXECUTE_TERMINAL_DEF, execute_terminal_command)

    # ── Media tools
    registry.register(PLAY_YOUTUBE_DEF, play_youtube)
    registry.register(CONTROL_MEDIA_DEF, control_media)

    # ── Communications tools
    registry.register(CHECK_EMAILS_DEF, check_emails)
    registry.register(CHECK_TELEGRAM_DEF, check_telegram)
    registry.register(SEND_DISCORD_DEF, send_discord_alert)

    logger.info(
        "tool_registry_built",
        tool_count=len(registry.get_tool_names()),
        tools=registry.get_tool_names(),
    )

    return registry
