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

# ─── Tool Policy Registry ─────────────────────────────────────────────────────
# Maps tool name (str) → PermissionLevel
# This is the authoritative source — the agent enforces it.

TOOL_POLICY: dict[str, PermissionLevel] = {
    # ── System Info Tools (Phase 2) — Read-only, safe to auto-execute ──────────
    "get_battery_status": PermissionLevel.SAFE,
    "get_cpu_usage": PermissionLevel.SAFE,
    "get_ram_usage": PermissionLevel.SAFE,
    "get_current_time": PermissionLevel.SAFE,
    "get_system_info": PermissionLevel.SAFE,
    "get_gpu_status": PermissionLevel.SAFE,

    # ── Application Tools (Phase 2) — External effects, need approval ──────────
    "open_application": PermissionLevel.CONFIRMATION,

    # ── Browser Tools (Phase 2) — Opens external URLs, need approval ───────────
    "open_url": PermissionLevel.CONFIRMATION,
    "web_search": PermissionLevel.CONFIRMATION,

    # ── Blocked forever ────────────────────────────────────────────────────────
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
