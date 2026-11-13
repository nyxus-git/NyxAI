"""
api/app/schemas/system.py

Pydantic schemas for /system telemetry and quick action endpoints.
"""

from typing import Any
from pydantic import BaseModel, Field


class AgentTelemetryInfo(BaseModel):
    id: str = Field(description="Unique agent identifier.")
    name: str = Field(description="Human-readable agent name.")
    status: str = Field(default="ready", description="Agent state: ready, active, busy.")
    role: str = Field(description="Agent responsibilities and specialty domain.")


class SystemTelemetryResponse(BaseModel):
    cpu: dict[str, Any] = Field(description="CPU percentage and core count.")
    ram: dict[str, Any] = Field(description="RAM usage, total, and percentage.")
    battery: dict[str, Any] = Field(description="Battery level and charging status.")
    gpu: dict[str, Any] = Field(description="GPU name, VRAM, and temperature.")
    uptime: str = Field(description="System uptime string.")
    agents: list[AgentTelemetryInfo] = Field(description="Active sub-agent swarm status.")


class QuickActionRequest(BaseModel):
    action: str = Field(description="Action identifier: activate_all_tasks, play_youtube, control_media, run_terminal")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the selected action.")


class QuickActionResponse(BaseModel):
    success: bool
    action: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)

