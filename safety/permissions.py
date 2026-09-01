"""
safety/permissions.py

Permission levels for NyxAI agent tools.

Every tool must have a permission level assigned in safety/policy.py.
The permission level determines whether a tool can be called automatically
or requires user confirmation.

Permission Hierarchy (from PRD Section 24):
  Level 1 — SAFE:         Auto-execute. Read-only, no side effects.
  Level 2 — CONFIRMATION: User must approve before execution.
  Level 3 — HIGH_RISK:    Explicit confirmation + extra validation required.
  Level 4 — BLOCKED:      Never execute under any circumstances.

Design note:
  In Phase 2, only SAFE tools auto-execute. CONFIRMATION tools return a
  pending state to the API — the client must send back an approval.
  HIGH_RISK and BLOCKED tools are rejected immediately.
"""

from enum import IntEnum


class PermissionLevel(IntEnum):
    """
    Defines the risk/trust level of a tool action.

    Use IntEnum so levels can be compared with < and > operators.
    A higher number = higher risk.
    """

    SAFE = 1
    """
    Automatically allowed. No side effects. Read-only.

    Examples: battery status, CPU usage, current time, system info.
    These can never harm the system or leak private data.
    """

    CONFIRMATION = 2
    """
    Requires explicit user approval before execution.

    Examples: open external URL, launch application, play music.
    These have external effects but are generally reversible.
    """

    HIGH_RISK = 3
    """
    Requires explicit confirmation plus additional validation.

    Examples: modify system config, manage services, install packages.
    These have potentially significant system effects.
    """

    BLOCKED = 4
    """
    Never execute. Permanently forbidden.

    Examples: rm -rf, format disk, arbitrary shell execution.
    These must NEVER be performed, regardless of user request.
    """


def can_auto_execute(level: PermissionLevel) -> bool:
    """
    Return True if a tool at this permission level can execute without user approval.

    In Phase 2: only SAFE tools auto-execute.
    CONFIRMATION, HIGH_RISK, and BLOCKED all require human review.

    Args:
        level: The tool's PermissionLevel.

    Returns:
        True if the tool can be called automatically.
    """
    return level == PermissionLevel.SAFE


def is_allowed(level: PermissionLevel) -> bool:
    """
    Return True if a tool at this permission level is ever allowed to execute.

    BLOCKED tools return False regardless of user confirmation.

    Args:
        level: The tool's PermissionLevel.

    Returns:
        True if the tool is not permanently blocked.
    """
    return level != PermissionLevel.BLOCKED
