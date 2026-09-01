"""
core/agent/schemas.py

Data models for the NyxAI agent tool system.

These schemas define the contract between:
  - The LLM (which decides what tool to call)
  - The tool registry (which executes the tool)
  - The API layer (which returns results to the client)

Design notes:
  - ToolDefinition uses JSON Schema format — this is what Ollama's tool calling
    API expects. Tools are registered once and converted to Ollama format.
  - ToolCall is the LLM's decision: which tool + what args.
  - ToolResult is what the tool returned after execution.
  - AgentResponse wraps everything together for the API response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    """Operating mode for the NyxAI agent."""

    COMPANION = "companion"  # Pure conversation, no tools
    AGENT = "agent"          # Tool-enabled agentic mode


# ─── Tool Definition ──────────────────────────────────────────────────────────


@dataclass
class ToolParameter:
    """
    A single parameter definition for a tool (JSON Schema style).

    Attributes:
        type: JSON Schema type (e.g., "string", "integer", "boolean").
        description: Human-readable description of the parameter.
        enum: Optional list of allowed values.
        required: Whether this parameter is required.
    """

    type: str
    description: str
    enum: list[str] | None = None
    required: bool = True

    def to_schema_dict(self) -> dict:
        """Convert to JSON Schema property dict for Ollama."""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        return schema


@dataclass
class ToolDefinition:
    """
    Full definition of a tool that NyxAI can call.

    This is the single source of truth for a tool. It contains:
      - Metadata (name, description) for the LLM to understand when to use it
      - Parameters schema for the LLM to know what arguments to provide
      - Permission level for the safety layer to enforce

    Attributes:
        name: Unique identifier. Must be snake_case. Used for dispatch.
        description: Natural language description of what this tool does.
                     This is shown to the LLM — write it clearly.
        parameters: Dict of parameter_name → ToolParameter.
        category: Tool category (e.g., "system", "browser", "files").
    """

    name: str
    description: str
    parameters: dict[str, ToolParameter] = field(default_factory=dict)
    category: str = "general"

    def to_ollama_format(self) -> dict:
        """
        Convert to Ollama's tool definition format.

        Ollama expects:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {
                    "type": "object",
                    "properties": { ... },
                    "required": [...]
                }
            }
        }
        """
        required_params = [
            name for name, param in self.parameters.items()
            if param.required
        ]
        properties = {
            name: param.to_schema_dict()
            for name, param in self.parameters.items()
        }

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_params,
                },
            },
        }


# ─── Tool Call & Result ───────────────────────────────────────────────────────


@dataclass
class ToolCall:
    """
    Represents the LLM's decision to call a specific tool.

    This is parsed from Ollama's response when it uses tool calling.

    Attributes:
        name: Name of the tool to call (matches ToolDefinition.name).
        arguments: Dict of argument_name → value as chosen by the LLM.
        call_id: Optional ID from Ollama for tracking multi-tool responses.
    """

    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass
class ToolResult:
    """
    Result from executing a tool.

    Attributes:
        tool_name: Which tool was called.
        success: Whether the tool executed successfully.
        data: The tool's output data (if success=True).
        error: Error message (if success=False).
        display_text: Human-readable summary of the result, injected into LLM context.
    """

    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    display_text: str = ""

    def to_llm_content(self) -> str:
        """
        Format the tool result as text to send back to the LLM.

        The LLM receives this as the content of a 'tool' message.
        """
        if self.success:
            return self.display_text or str(self.data)
        return f"Tool '{self.tool_name}' failed: {self.error}"


# ─── Agent Response ───────────────────────────────────────────────────────────


@dataclass
class AgentResponse:
    """
    Complete response from the NyxAI agent.

    This wraps the final natural language response along with
    metadata about any tool that was called.

    Attributes:
        content: Final natural language response to return to the user.
        conversation_id: UUID of the conversation (for multi-turn context).
        model: LLM model name used.
        tool_used: Name of the tool that was called, if any.
        tool_result: Raw tool output data, if a tool was called.
        iterations: How many tool call iterations were needed.
    """

    content: str
    model: str
    tool_used: str | None = None
    tool_result: dict[str, Any] | None = None
    iterations: int = 0
