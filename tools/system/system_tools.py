"""
tools/system/system_tools.py

System information tools for NyxAI.

All tools here are read-only and safe to auto-execute (PermissionLevel.SAFE).
They use psutil for cross-platform system metrics and standard library modules
for other information.

Tools:
  - get_battery_status: Battery percentage and charging state
  - get_cpu_usage: CPU utilization percentage
  - get_ram_usage: RAM used, available, and total
  - get_current_time: Current date and time
  - get_system_info: OS, kernel, hostname, uptime
  - get_gpu_status: NVIDIA GPU info via nvidia-smi (graceful fallback if unavailable)
"""

import platform
import shutil
import subprocess
from datetime import datetime, timezone

import psutil

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)


# ─── Tool Definitions ─────────────────────────────────────────────────────────
# These ToolDefinition objects are imported by the tool_registry.

GET_BATTERY_DEF = ToolDefinition(
    name="get_battery_status",
    description=(
        "Get the current battery level and charging status of the laptop. "
        "Returns battery percentage, whether it's plugged in, and charging state."
    ),
    parameters={},  # No parameters needed
    category="system",
)

GET_CPU_DEF = ToolDefinition(
    name="get_cpu_usage",
    description=(
        "Get the current CPU usage percentage of the system. "
        "Returns overall CPU utilization across all cores."
    ),
    parameters={},
    category="system",
)

GET_RAM_DEF = ToolDefinition(
    name="get_ram_usage",
    description=(
        "Get the current RAM (memory) usage. "
        "Returns used memory, available memory, total memory, and usage percentage."
    ),
    parameters={},
    category="system",
)

GET_TIME_DEF = ToolDefinition(
    name="get_current_time",
    description=(
        "Get the current date and time. "
        "Returns the current local time and date."
    ),
    parameters={},
    category="system",
)

GET_SYSINFO_DEF = ToolDefinition(
    name="get_system_info",
    description=(
        "Get general system information including OS name, kernel version, hostname, "
        "and system uptime. Useful for answering questions about the computer."
    ),
    parameters={},
    category="system",
)

GET_GPU_DEF = ToolDefinition(
    name="get_gpu_status",
    description=(
        "Get the current NVIDIA GPU status including GPU name, temperature, "
        "memory usage, and GPU utilization. "
        "Returns an error if no NVIDIA GPU is found."
    ),
    parameters={},
    category="system",
)


# ─── Tool Implementations ─────────────────────────────────────────────────────


def get_battery_status() -> ToolResult:
    """
    Return the current battery level and charging status.

    Returns:
        ToolResult with data:
          - percent (int): Battery percentage (0-100)
          - plugged_in (bool): Whether the charger is connected
          - status (str): Human-readable status ("Charging", "Discharging", "Full", "Unknown")
    """
    logger.debug("tool_get_battery_status")

    battery = psutil.sensors_battery()

    if battery is None:
        return ToolResult(
            tool_name="get_battery_status",
            success=False,
            error="No battery detected. This may be a desktop computer.",
        )

    percent = round(battery.percent, 1)
    plugged_in = battery.power_plugged

    if plugged_in and percent >= 99:
        status = "Full"
    elif plugged_in:
        status = "Charging"
    else:
        status = "Discharging"

    data = {
        "percent": percent,
        "plugged_in": plugged_in,
        "status": status,
    }

    display = (
        f"Battery: {percent}% — {status}"
        + (" 🔌" if plugged_in else " 🔋")
    )

    logger.info("tool_battery_result", percent=percent, status=status)

    return ToolResult(
        tool_name="get_battery_status",
        success=True,
        data=data,
        display_text=display,
    )


def get_cpu_usage() -> ToolResult:
    """
    Return the current CPU utilization percentage.

    Uses a 0.5-second sample interval for accuracy.

    Returns:
        ToolResult with data:
          - percent (float): Overall CPU usage (0.0 - 100.0)
          - core_count (int): Number of logical CPU cores
    """
    logger.debug("tool_get_cpu_usage")

    # interval=0.5 means psutil measures over half a second for accuracy
    percent = psutil.cpu_percent(interval=0.5)
    core_count = psutil.cpu_count(logical=True)

    data = {
        "percent": percent,
        "core_count": core_count,
    }

    display = f"CPU usage: {percent}% across {core_count} logical cores"

    logger.info("tool_cpu_result", percent=percent)

    return ToolResult(
        tool_name="get_cpu_usage",
        success=True,
        data=data,
        display_text=display,
    )


def get_ram_usage() -> ToolResult:
    """
    Return the current RAM usage statistics.

    Returns:
        ToolResult with data:
          - used_gb (float): RAM in use (GB)
          - available_gb (float): RAM available (GB)
          - total_gb (float): Total RAM installed (GB)
          - percent (float): Percentage used
    """
    logger.debug("tool_get_ram_usage")

    mem = psutil.virtual_memory()

    def to_gb(bytes_: int) -> float:
        return round(bytes_ / (1024 ** 3), 2)

    data = {
        "used_gb": to_gb(mem.used),
        "available_gb": to_gb(mem.available),
        "total_gb": to_gb(mem.total),
        "percent": round(mem.percent, 1),
    }

    display = (
        f"RAM: {data['used_gb']} GB used / {data['total_gb']} GB total "
        f"({data['percent']}% in use, {data['available_gb']} GB free)"
    )

    logger.info("tool_ram_result", percent=data["percent"])

    return ToolResult(
        tool_name="get_ram_usage",
        success=True,
        data=data,
        display_text=display,
    )


def get_current_time() -> ToolResult:
    """
    Return the current local date and time.

    Returns:
        ToolResult with data:
          - datetime (str): ISO-8601 formatted local datetime
          - date (str): Human-readable date
          - time (str): Human-readable time (12-hour format)
          - day_of_week (str): Day name (e.g. "Monday")
    """
    logger.debug("tool_get_current_time")

    now = datetime.now()

    data = {
        "datetime": now.isoformat(),
        "date": now.strftime("%B %d, %Y"),
        "time": now.strftime("%I:%M %p"),
        "day_of_week": now.strftime("%A"),
    }

    display = f"Current time: {data['day_of_week']}, {data['date']} at {data['time']}"

    logger.info("tool_time_result", datetime=data["datetime"])

    return ToolResult(
        tool_name="get_current_time",
        success=True,
        data=data,
        display_text=display,
    )


def get_system_info() -> ToolResult:
    """
    Return general system information.

    Returns:
        ToolResult with data:
          - os (str): Operating system name and version
          - kernel (str): Kernel version
          - hostname (str): Machine hostname
          - architecture (str): CPU architecture
          - uptime_hours (float): Hours since last boot
    """
    logger.debug("tool_get_system_info")

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    uptime_hours = round(uptime.total_seconds() / 3600, 1)

    data = {
        "os": f"{platform.system()} {platform.version()[:40]}",
        "os_name": platform.system(),
        "kernel": platform.release(),
        "hostname": platform.node(),
        "architecture": platform.machine(),
        "uptime_hours": uptime_hours,
        "python_version": platform.python_version(),
    }

    display = (
        f"System: {data['os_name']} | Kernel: {data['kernel']} | "
        f"Host: {data['hostname']} | Arch: {data['architecture']} | "
        f"Uptime: {uptime_hours}h"
    )

    logger.info("tool_sysinfo_result", hostname=data["hostname"])

    return ToolResult(
        tool_name="get_system_info",
        success=True,
        data=data,
        display_text=display,
    )


def get_gpu_status() -> ToolResult:
    """
    Return NVIDIA GPU status via nvidia-smi.

    Falls back gracefully if nvidia-smi is not available.

    Returns:
        ToolResult with data:
          - name (str): GPU model name
          - temperature_c (int): GPU temperature in Celsius
          - memory_used_mb (int): VRAM used (MB)
          - memory_total_mb (int): Total VRAM (MB)
          - gpu_utilization_percent (int): GPU compute usage (%)
    """
    logger.debug("tool_get_gpu_status")

    if not shutil.which("nvidia-smi"):
        return ToolResult(
            tool_name="get_gpu_status",
            success=False,
            error=(
                "nvidia-smi not found. Either this system has no NVIDIA GPU, "
                "or the NVIDIA drivers are not installed."
            ),
        )

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return ToolResult(
                tool_name="get_gpu_status",
                success=False,
                error=f"nvidia-smi returned error: {result.stderr.strip()[:100]}",
            )

        parts = [p.strip() for p in result.stdout.strip().split(",")]
        if len(parts) < 5:
            return ToolResult(
                tool_name="get_gpu_status",
                success=False,
                error=f"Unexpected nvidia-smi output: {result.stdout.strip()[:100]}",
            )

        data = {
            "name": parts[0],
            "temperature_c": int(parts[1]),
            "memory_used_mb": int(parts[2]),
            "memory_total_mb": int(parts[3]),
            "gpu_utilization_percent": int(parts[4]),
        }

        display = (
            f"GPU: {data['name']} | Temp: {data['temperature_c']}°C | "
            f"VRAM: {data['memory_used_mb']}MB / {data['memory_total_mb']}MB | "
            f"GPU load: {data['gpu_utilization_percent']}%"
        )

        logger.info(
            "tool_gpu_result",
            name=data["name"],
            temp=data["temperature_c"],
            vram_used=data["memory_used_mb"],
        )

        return ToolResult(
            tool_name="get_gpu_status",
            success=True,
            data=data,
            display_text=display,
        )

    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name="get_gpu_status",
            success=False,
            error="nvidia-smi timed out after 5 seconds.",
        )
    except Exception as e:
        logger.error("tool_gpu_error", error=str(e))
        return ToolResult(
            tool_name="get_gpu_status",
            success=False,
            error=f"Unexpected error reading GPU status: {str(e)}",
        )
