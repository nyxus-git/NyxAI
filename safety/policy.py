"""
safety/policy.py

Central policy mapping: tool name → PermissionLevel.

This is the single source of truth for what each tool is allowed to do.
The NyxAgent checks this before any tool execution.

Adding a new tool:
  1. Register it in tools/ and core/agent/tool_registry.py
  2. Add its permission level here in TOOL_POLICY
  3. Never skip this step.

Design note:
  Defaulting to BLOCKED for unknown tools means any unregistered or
  typo'd tool name will be safely rejected.
"""

from safety.permissions import PermissionLevel

# Tool Policy Registry
# Maps tool name (str) → PermissionLevel
# This is the authoritative source — the agent enforces it.

TOOL_POLICY: dict[str, PermissionLevel] = {
    # ── System Info Tools  — Read-only, safe to auto-execute
    "get_battery_status": PermissionLevel.SAFE,
    "get_cpu_usage": PermissionLevel.SAFE,
    "get_ram_usage": PermissionLevel.SAFE,
    "get_current_time": PermissionLevel.SAFE,
    "get_system_info": PermissionLevel.SAFE,
    "get_gpu_status": PermissionLevel.SAFE,

    # ── Read-only File, Web, Task & Planning Tools
    "list_directory": PermissionLevel.SAFE,
    "read_file": PermissionLevel.SAFE,
    "search_files": PermissionLevel.SAFE,
    "read_webpage": PermissionLevel.SAFE,
    "add_task": PermissionLevel.SAFE,
    "list_tasks": PermissionLevel.SAFE,
    "complete_task": PermissionLevel.SAFE,
    "set_reminder": PermissionLevel.SAFE,
    "create_plan": PermissionLevel.SAFE,
    "update_plan": PermissionLevel.SAFE,

    # ── Application & File Mutation Tools — Require confirmation unless approved
    "open_application": PermissionLevel.CONFIRMATION,
    "move_file": PermissionLevel.CONFIRMATION,
    "copy_file": PermissionLevel.CONFIRMATION,
    "delete_file": PermissionLevel.CONFIRMATION,

    # ── Browser Tools  — Opens external URLs, need approval
    "open_url": PermissionLevel.CONFIRMATION,
    "web_search": PermissionLevel.CONFIRMATION,

    # ── Blocked forever
    # Shell execution is NEVER exposed to the LLM directly.
    "run_shell_command": PermissionLevel.BLOCKED,
    "execute_python": PermissionLevel.BLOCKED,
    "rm_files": PermissionLevel.BLOCKED,
}


def get_permission_level(tool_name: str) -> PermissionLevel:
    """
    Look up the permission level for a given tool name.

    Returns BLOCKED for any tool not in the policy registry.
    This fail-safe ensures unknown tools never execute.

    Args:
        tool_name: The name of the tool to look up.

    Returns:
        PermissionLevel for the tool. Defaults to BLOCKED if unknown.
    """
    return TOOL_POLICY.get(tool_name, PermissionLevel.BLOCKED)
