"""
core/agent/agent.py

NyxAI Agent — the agentic reasoning loop.

This module implements the core agent that can use tools to complete tasks.
It sits above the LLM provider and uses the ToolRegistry to dispatch tool
calls when the LLM decides to use them.

How it works (single agent turn):
  1. Build message list: [system_prompt] + [history] + [user_message]
  2. Call llm.chat_with_tools() with all registered tools
  3. If LLM returns text → done, return the response
  4. If LLM returns a tool call:
      a. Check safety policy via ToolRegistry.dispatch()
      b. Execute the tool
      c. Append tool result as a "tool" message
      d. Call LLM again with the tool result → get final natural response
  5. Repeat up to MAX_ITERATIONS to handle multi-tool tasks
  6. Return AgentResponse with result + metadata

Design notes:
  - MAX_ITERATIONS caps the loop to prevent infinite tool calling
  - The agent uses a LOWER temperature (0.5) for tool selection vs. companion chat
  - Tool results are fed back as the 'tool' message role (Ollama multi-turn tool format)
  - If the LLM keeps calling tools beyond MAX_ITERATIONS, we return the last tool result
    as a fallback response instead of silently failing
"""

from __future__ import annotations

import uuid
import aiosqlite

from core.agent.schemas import AgentResponse, ToolCall, ToolResult
from core.agent.tool_registry import ToolNotFoundError, ToolPermissionError, ToolRegistry, ToolValidationError
from core.brain.llm import LLMProvider, Message, MessageRole
from core.brain.prompts import get_system_prompt
from core.logging import get_logger

logger = get_logger(__name__)

# Maximum number of tool call iterations per agent turn.
# Prevents infinite loops if the LLM keeps calling tools without converging.
MAX_ITERATIONS = 8

# Agent mode system prompt extension — appended to the base system prompt
# when running in agent mode to prime the model for tool use.
AGENT_SYSTEM_PROMPT_SUFFIX = """

## Agent Mode — Tool Use
You now have access to tools that let you take real actions on this Linux computer, read files, search the web, and manage tasks.

When the user asks for something you can do with a tool:
  - Use the appropriate tool — do NOT make up information.
  - For complex requests, THINK step-by-step. You can use multiple tools sequentially to achieve a goal.
  - IMPORTANT: If a task requires more than one step, use `create_plan` first to write down what you will do. As you complete steps, use `update_plan` to track your progress.
  - Do NOT call multiple tools in one response unless the user explicitly asks for multiple things.
  - After a tool returns its result, evaluate if you need to use another tool to finish the job, or respond naturally in the user's language.

When the user asks something conversational that does NOT need a tool:
  - Respond directly — do not call a tool unnecessarily.
  - Only use tools when they add real value.

Tool use examples:
  - "What's my battery?" → use get_battery_status
  - "Summarize my notes.txt" → use read_file on notes.txt
  - "Research quantum computing" → use web_search, then read_webpage on the best result.
  - "How are you?" → respond directly, no tool needed
"""


class NyxAgent:
    """
    The NyxAI agent that combines LLM reasoning with tool execution.

    Wraps an LLMProvider and a ToolRegistry to create an agent capable
    of using tools to help the user.

    Args:
        llm_provider: The LLM backend to use for reasoning.
        tool_registry: The registry of available tools.
        max_iterations: Maximum tool call iterations per turn. Default: 3.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        self._llm = llm_provider
        self._registry = tool_registry
        self._max_iterations = max_iterations
        self._tools_for_ollama = tool_registry.get_tools_for_ollama()

        logger.info(
            "nyx_agent_initialized",
            model=llm_provider.get_model_name(),
            tool_count=len(self._tools_for_ollama),
            max_iterations=max_iterations,
        )

    async def run(
        self,
        message: str,
        history: list[Message] | None = None,
        conversation_id: str | None = None,
    ) -> AgentResponse:
        """
        Process a user message with full tool-calling capability.

        This is the main entry point for agent mode. It manages the entire
        plan → tool → observe → respond loop.

        Args:
            message: The user's input text.
            history: Previous conversation messages (user + assistant turns).
                     System prompt is added automatically.

        Returns:
            AgentResponse with the final response content and tool metadata.
        """
        history = history or []
        conv_id = str(uuid.uuid4())[:8]  # Short ID for log correlation

        logger.info(
            "agent_run_start",
            conversation_prefix=conv_id,
            message_preview=message[:60],
            history_length=len(history),
        )

        # Build initial message list
        # [system_prompt + agent_suffix + active_plan] + [history] + [user_message]
        system_content = get_system_prompt(compact=False) + AGENT_SYSTEM_PROMPT_SUFFIX
        
        # Inject active plan if it exists
        if conversation_id:
            try:
                async with aiosqlite.connect("./data/nyx_memory.db") as conn:
                    cursor = await conn.execute(
                        "SELECT content FROM plans WHERE conversation_id = ? AND status = 'active'",
                        (conversation_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        system_content += f"\n\n## ACTIVE PLAN\nYou have an active plan for this task:\n{row[0]}"
            except Exception as e:
                logger.error("agent_fetch_plan_failed", error=str(e))
                
        system_message = Message(role=MessageRole.SYSTEM, content=system_content)
        user_message = Message(role=MessageRole.USER, content=message)

        # Working message list — grows with each tool call iteration
        messages: list[Message] = [system_message] + history + [user_message]

        tool_used: str | None = None
        tool_result_data: dict | None = None
        iterations = 0

        # ── Agentic loop
        while iterations < self._max_iterations:
            iterations += 1

            logger.debug(
                "agent_llm_call",
                conversation_prefix=conv_id,
                iteration=iterations,
                message_count=len(messages),
            )

            # Call LLM with tools
            llm_response = await self._llm.chat_with_tools(
                messages=messages,
                tools=self._tools_for_ollama,
                temperature=0.5,  # Lower temp for more deterministic tool selection
            )

            # Case 1: LLM responded with text — no tool call needed
            if not llm_response.has_tool_calls:
                logger.info(
                    "agent_responded_directly",
                    conversation_prefix=conv_id,
                    iteration=iterations,
                )
                return AgentResponse(
                    content=llm_response.content,
                    model=llm_response.model,
                    tool_used=tool_used,
                    tool_result=tool_result_data,
                    iterations=iterations,
                )

            # Case 2: LLM wants to call a tool
            # Process the first tool call (handle one at a time for safety)
            tool_call: ToolCall = llm_response.tool_calls[0]

            logger.info(
                "agent_tool_call_received",
                conversation_prefix=conv_id,
                iteration=iterations,
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
            )

            # Append the LLM's tool call decision to the message history
            # This is required by Ollama's multi-turn tool format:
            # the assistant message that contained the tool_call must be in history
            assistant_tool_msg = Message(
                role=MessageRole.ASSISTANT,
                content=llm_response.content or "",  # Usually empty when calling a tool
            )
            messages.append(assistant_tool_msg)

            # Execute the tool via the registry (enforces safety + validation)
            tool_result = await self._execute_tool(tool_call, conv_id)

            # Track which tool was used (for the AgentResponse metadata)
            tool_used = tool_call.name
            tool_result_data = tool_result.data

            # Append tool result as a tool message for the LLM
            # This tells the LLM what the tool returned so it can craft a response
            tool_result_message = Message(
                role=MessageRole.USER,  # Some models use 'tool' role; for compatibility we use user
                content=f"[Tool: {tool_call.name}]\n{tool_result.to_llm_content()}",
            )
            messages.append(tool_result_message)

            # If tool failed, ask LLM to inform user gracefully
            if not tool_result.success:
                logger.warning(
                    "agent_tool_failed",
                    conversation_prefix=conv_id,
                    tool_name=tool_call.name,
                    error=tool_result.error,
                )
                # Continue loop — let LLM respond to the failure result

            # If tool returned pending_confirmation, return immediately
            if (
                tool_result.data.get("status") == "pending_confirmation"
            ):
                logger.info(
                    "agent_tool_needs_confirmation",
                    tool_name=tool_call.name,
                )
                return AgentResponse(
                    content=(
                        f"I'd like to {tool_call.name.replace('_', ' ')} for you, "
                        f"but I need your confirmation first. "
                        f"This action requires approval before it can run."
                    ),
                    model=llm_response.model,
                    tool_used=tool_call.name,
                    tool_result={"status": "pending_confirmation"},
                    iterations=iterations,
                )

        # ── Max iterations reached — return last content if available
        logger.warning(
            "agent_max_iterations_reached",
            conversation_prefix=conv_id,
            max_iterations=self._max_iterations,
        )

        # Make one final LLM call to synthesize a response from what we have
        final_response = await self._llm.chat(messages=messages)

        return AgentResponse(
            content=final_response.content,
            model=final_response.model,
            tool_used=tool_used,
            tool_result=tool_result_data,
            iterations=iterations,
        )

    async def _execute_tool(self, tool_call: ToolCall, conv_id: str) -> ToolResult:
        """
        Execute a tool call with error handling.

        Wraps ToolRegistry.dispatch() to catch registry-level errors and
        convert them to ToolResult objects so the agent loop can continue.

        Args:
            tool_call: The tool call from the LLM.
            conv_id: Conversation prefix for log correlation.

        Returns:
            ToolResult — always returns a result, never raises.
        """
        try:
            result = await self._registry.dispatch(tool_call)
            return result

        except ToolNotFoundError as e:
            logger.warning("agent_tool_not_found", tool_name=tool_call.name)
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                display_text=f"I tried to use '{tool_call.name}' but it's not available.",
            )

        except ToolPermissionError as e:
            logger.warning("agent_tool_permission_denied", tool_name=tool_call.name)
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                display_text=(
                    f"'{tool_call.name}' requires permission level {e.level.name} "
                    f"and cannot be executed automatically."
                ),
            )

        except ToolValidationError as e:
            logger.warning("agent_tool_validation_failed", tool_name=tool_call.name)
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                display_text=f"The arguments for '{tool_call.name}' failed safety validation.",
            )

        except Exception as e:
            logger.exception("agent_tool_unexpected_error", tool_name=tool_call.name, error=str(e))
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                display_text=f"An unexpected error occurred while running '{tool_call.name}'.",
            )
