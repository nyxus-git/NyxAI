"""
tools/terminal/terminal_tools.py

Controlled terminal execution engine for NyxAI.

Allows the agent to execute sanctioned Linux shell commands (e.g. git status,
docker ps, cargo test, free -h, htop) with output capture, strict safety checks,
and timeout protection.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import time
from typing import Any

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

# Dangerous shell commands that are unconditionally prohibited by security policy
_PROHIBITED_COMMANDS: list[re.Pattern] = [
    re.compile(r"\b(sudo|su)\b", re.IGNORECASE),
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME)", re.IGNORECASE),  # rm -rf / or root/home paths
    re.compile(r"\bmkfs(\.[a-z0-9]+)?\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # fork bomb
    re.compile(r">\s*/dev/(sd[a-z]|nvme[0-9]|vd[a-z]|loop[0-9])", re.IGNORECASE),  # Raw disk writes
    re.compile(r"\bchmod\s+(-R\s+)?777\s+/\b", re.IGNORECASE),
    re.compile(r"\b(shutdown|reboot|poweroff|halt|init\s+[06])\b", re.IGNORECASE),  # Disallow abrupt reboots/shutdowns
]

# Max output characters returned to prevent prompt context bloat
MAX_OUTPUT_CHARS = 4000

EXECUTE_TERMINAL_DEF = ToolDefinition(
    name="execute_terminal_command",
    description=(
        "Execute a shell command on the local Linux terminal and return its output. "
        "Use this to inspect system status, git branches, running processes, run tests, "
        "or compile projects. "
        "Examples: 'git status', 'df -h', 'uptime', 'pytest', 'docker ps', 'free -m'."
    ),
    parameters={
        "command": ToolParameter(
            type="string",
            description="The exact bash command to execute (e.g., 'git status', 'free -h').",
            required=True,
        ),
        "timeout_seconds": ToolParameter(
            type="number",
            description="Maximum execution time before termination in seconds (default: 15.0).",
            required=False,
        ),
    },
    category="terminal",
)


async def execute_terminal_command(
    command: str,
    timeout_seconds: float = 15.0,
    cwd: str | None = None,
) -> ToolResult:
    """
    Execute a sandboxed shell command asynchronously and return stdout/stderr.

    Args:
        command: The bash command string to run.
        timeout_seconds: Maximum execution time before termination (default: 15s).
        cwd: Optional working directory for command execution.

    Returns:
        ToolResult with command output, execution time, and exit status.
    """
    if not isinstance(command, str):
        command = str(command) if command is not None else ""

    clean_cmd = command.strip()
    if not clean_cmd:
        return ToolResult(
            tool_name="execute_terminal_command",
            success=False,
            error="Command cannot be empty.",
        )

    # Coerce and clamp timeout safely
    try:
        timeout_val = max(1.0, min(120.0, float(timeout_seconds)))
    except (ValueError, TypeError):
        timeout_val = 15.0

    # 1. Security blocklist check
    for pattern in _PROHIBITED_COMMANDS:
        if pattern.search(clean_cmd):
            logger.warning("terminal_command_prohibited", command=clean_cmd)
            return ToolResult(
                tool_name="execute_terminal_command",
                success=False,
                error=f"Command '{clean_cmd}' is prohibited by safety policy.",
                display_text=f"The command '{clean_cmd}' is blocked for security reasons.",
            )

    logger.info("terminal_command_executing", command=clean_cmd, timeout_s=timeout_val)
    start_t = time.time()
    proc = None

    try:
        proc = await asyncio.create_subprocess_shell(
            clean_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,  # Isolate in process group for clean kill
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_val,
        )

        elapsed = round(time.time() - start_t, 3)
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        returncode = proc.returncode if proc.returncode is not None else 0

        # Truncate if output exceeds limit
        truncated_stdout = stdout[:MAX_OUTPUT_CHARS]
        if len(stdout) > MAX_OUTPUT_CHARS:
            truncated_stdout += f"\n... [Output truncated: {len(stdout) - MAX_OUTPUT_CHARS} chars omitted]"

        success = (returncode == 0)

        output_summary = truncated_stdout if truncated_stdout else stderr
        display = f"$ {clean_cmd}\n{output_summary}" if output_summary else f"$ {clean_cmd}\n(No output, exited with code {returncode})"

        logger.info(
            "terminal_command_completed",
            command=clean_cmd,
            returncode=returncode,
            elapsed_s=elapsed,
        )

        return ToolResult(
            tool_name="execute_terminal_command",
            success=success,
            data={
                "command": clean_cmd,
                "returncode": returncode,
                "stdout": truncated_stdout,
                "stderr": stderr[:1000],
                "elapsed_s": elapsed,
            },
            display_text=display,
        )

    except asyncio.TimeoutError:
        logger.warning("terminal_command_timed_out", command=clean_cmd, timeout_s=timeout_val)
        if proc is not None:
            try:
                # Terminate the entire process group
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                await proc.wait()
            except Exception:
                pass

        return ToolResult(
            tool_name="execute_terminal_command",
            success=False,
            error=f"Command '{clean_cmd}' timed out after {timeout_val} seconds.",
            display_text=f"Command timed out after {timeout_val}s.",
        )
    except Exception as e:
        logger.exception("terminal_command_failed", command=clean_cmd, error=str(e))
        return ToolResult(
            tool_name="execute_terminal_command",
            success=False,
            error=f"Execution failed: {str(e)}",
        )
