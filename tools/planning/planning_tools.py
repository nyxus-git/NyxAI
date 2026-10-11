"""
tools/planning/planning_tools.py

Planning tools for NyxAI Advanced Agent.
These tools allow the agent to create and update multi-step plans
to organize complex task execution over multiple turns.
"""

from datetime import datetime, timezone
import aiosqlite

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

# DB path hardcoded for now, same as task_tools.py
DB_PATH = "./data/nyx_memory.db"

# Tool Definitions

CREATE_PLAN_DEF = ToolDefinition(
    name="create_plan",
    description=(
        "Create a multi-step plan to solve a complex task. "
        "Use this tool before executing complex operations to break them down into steps."
    ),
    parameters={
        "conversation_id": ToolParameter(
            type="string",
            description="The current conversation ID. Pass the conversation context UUID.",
            required=True,
        ),
        "content": ToolParameter(
            type="string",
            description="The full detailed plan in markdown format, outlining each step.",
            required=True,
        ),
    },
    category="planning",
)

UPDATE_PLAN_DEF = ToolDefinition(
    name="update_plan",
    description=(
        "Update the active plan for the current conversation. "
        "Use this to mark steps as completed, add new steps, or revise the plan based on new information."
    ),
    parameters={
        "conversation_id": ToolParameter(
            type="string",
            description="The current conversation ID.",
            required=True,
        ),
        "content": ToolParameter(
            type="string",
            description="The updated full plan in markdown format.",
            required=True,
        ),
    },
    category="planning",
)


# Tool Implementations

async def create_plan(conversation_id: str, content: str) -> ToolResult:
    """Create a new plan."""
    logger.info("tool_create_plan", conversation_id=conversation_id)
    try:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(DB_PATH) as conn:
            # First, check if there's already an active plan and mark it inactive
            await conn.execute(
                "UPDATE plans SET status = 'inactive', updated_at = ? WHERE conversation_id = ? AND status = 'active'",
                (now, conversation_id),
            )
            
            cursor = await conn.execute(
                "INSERT INTO plans (conversation_id, content, status, created_at, updated_at) VALUES (?, ?, 'active', ?, ?)",
                (conversation_id, content, now, now),
            )
            await conn.commit()
            plan_id = cursor.lastrowid
            
        return ToolResult(
            tool_name="create_plan",
            success=True,
            data={"id": plan_id, "conversation_id": conversation_id, "status": "active"},
            display_text=f"Plan created successfully (ID: {plan_id}).\n\n{content}",
        )
    except Exception as e:
        logger.error("tool_create_plan_failed", error=str(e))
        return ToolResult(
            tool_name="create_plan",
            success=False,
            error=f"Failed to create plan: {str(e)}",
        )


async def update_plan(conversation_id: str, content: str) -> ToolResult:
    """Update an existing active plan."""
    logger.info("tool_update_plan", conversation_id=conversation_id)
    try:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(DB_PATH) as conn:
            # Update the active plan
            cursor = await conn.execute(
                "UPDATE plans SET content = ?, updated_at = ? WHERE conversation_id = ? AND status = 'active'",
                (content, now, conversation_id),
            )
            await conn.commit()
            
            if cursor.rowcount == 0:
                return ToolResult(
                    tool_name="update_plan",
                    success=False,
                    error=f"No active plan found for conversation {conversation_id}. Use create_plan first.",
                )
                
        return ToolResult(
            tool_name="update_plan",
            success=True,
            data={"conversation_id": conversation_id, "status": "active"},
            display_text=f"Plan updated successfully.\n\n{content}",
        )
    except Exception as e:
        logger.error("tool_update_plan_failed", error=str(e))
        return ToolResult(
            tool_name="update_plan",
            success=False,
            error=f"Failed to update plan: {str(e)}",
        )
