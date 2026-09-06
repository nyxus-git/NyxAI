"""
tools/tasks/task_tools.py

Task and To-Do management tools for NyxAI.

These tools allow the agent to add, list, and complete tasks.
Tasks are stored in the SQLite database via direct connection.
"""

from datetime import datetime, timezone, timedelta
import aiosqlite

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

# Hardcoded DB path for tools (could be passed via registry context in future)
DB_PATH = "./data/nyx_memory.db"


# ─── Tool Definitions ─────────────────────────────────────────────────────────

ADD_TASK_DEF = ToolDefinition(
    name="add_task",
    description=(
        "Add a new task to the user's to-do list. "
        "Use this when the user asks you to remind them to do something, "
        "or tells you to add something to their task list."
    ),
    parameters={
        "title": ToolParameter(
            type="string",
            description="The description of the task (e.g. 'Buy milk', 'Reply to John\\'s email').",
            required=True,
        ),
    },
    category="tasks",
)

LIST_TASKS_DEF = ToolDefinition(
    name="list_tasks",
    description=(
        "List all pending tasks on the user's to-do list. "
        "Use this when the user asks what they need to do, or what's on their task list."
    ),
    parameters={},
    category="tasks",
)

COMPLETE_TASK_DEF = ToolDefinition(
    name="complete_task",
    description=(
        "Mark a specific task as completed. "
        "Use this when the user says they finished a task, or asks you to cross it off."
    ),
    parameters={
        "task_id": ToolParameter(
            type="integer",
            description="The ID of the task to complete (must be a number).",
            required=True,
        ),
    },
    category="tasks",
)

SET_REMINDER_DEF = ToolDefinition(
    name="set_reminder",
    description=(
        "Set a reminder for a specific task. "
        "Use this when the user asks you to remind them to do something in a certain amount of time."
    ),
    parameters={
        "title": ToolParameter(
            type="string",
            description="The description of the reminder (e.g. 'Check the oven').",
            required=True,
        ),
        "minutes_from_now": ToolParameter(
            type="integer",
            description="How many minutes from now to trigger the reminder.",
            required=True,
        ),
    },
    category="tasks",
)


# ─── Tool Implementations ─────────────────────────────────────────────────────

async def add_task(title: str) -> ToolResult:
    """Add a new task."""
    logger.info("tool_add_task", title=title)
    try:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                "INSERT INTO tasks (title, status, created_at, updated_at) VALUES (?, 'pending', ?, ?)",
                (title, now, now),
            )
            await conn.commit()
            task_id = cursor.lastrowid
            
        data = {"id": task_id, "title": title, "status": "pending"}
        return ToolResult(
            tool_name="add_task",
            success=True,
            data=data,
            display_text=f"Added task: '{title}' (ID: {task_id})",
        )
    except Exception as e:
        logger.error("tool_add_task_failed", error=str(e))
        return ToolResult(
            tool_name="add_task",
            success=False,
            error=f"Failed to add task: {str(e)}",
        )


async def list_tasks() -> ToolResult:
    """List pending tasks."""
    logger.info("tool_list_tasks")
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT id, title, created_at FROM tasks WHERE status = 'pending' ORDER BY id ASC"
            )
            rows = await cursor.fetchall()
            
        tasks = [{"id": row["id"], "title": row["title"], "created_at": row["created_at"]} for row in rows]
        
        if not tasks:
            return ToolResult(
                tool_name="list_tasks",
                success=True,
                data={"count": 0},
                display_text="There are no pending tasks.",
            )
            
        output = "Pending Tasks:\n"
        for t in tasks:
            output += f"- [ID: {t['id']}] {t['title']}\n"
            
        return ToolResult(
            tool_name="list_tasks",
            success=True,
            data={"count": len(tasks), "tasks": tasks},
            display_text=output,
        )
    except Exception as e:
        logger.error("tool_list_tasks_failed", error=str(e))
        return ToolResult(
            tool_name="list_tasks",
            success=False,
            error=f"Failed to list tasks: {str(e)}",
        )


async def complete_task(task_id: int) -> ToolResult:
    """Mark a task as completed."""
    logger.info("tool_complete_task", task_id=task_id)
    try:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                "UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            await conn.commit()
            
            if cursor.rowcount == 0:
                return ToolResult(
                    tool_name="complete_task",
                    success=False,
                    error=f"No pending task found with ID {task_id}.",
                )
                
        return ToolResult(
            tool_name="complete_task",
            success=True,
            data={"id": task_id, "status": "completed"},
            display_text=f"Marked task {task_id} as completed.",
        )
    except Exception as e:
        logger.error("tool_complete_task_failed", error=str(e))
        return ToolResult(
            tool_name="complete_task",
            success=False,
            error=f"Failed to complete task: {str(e)}",
        )


async def set_reminder(title: str, minutes_from_now: int) -> ToolResult:
    """Set a reminder."""
    logger.info("tool_set_reminder", title=title, minutes=minutes_from_now)
    try:
        now = datetime.now(timezone.utc)
        due_at = (now + timedelta(minutes=minutes_from_now)).isoformat()
        now_iso = now.isoformat()
        
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                "INSERT INTO reminders (title, due_at, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
                (title, due_at, now_iso, now_iso),
            )
            await conn.commit()
            rem_id = cursor.lastrowid
            
        return ToolResult(
            tool_name="set_reminder",
            success=True,
            data={"id": rem_id, "title": title, "due_at": due_at},
            display_text=f"Reminder set: '{title}' in {minutes_from_now} minutes.",
        )
    except Exception as e:
        logger.error("tool_set_reminder_failed", error=str(e))
        return ToolResult(
            tool_name="set_reminder",
            success=False,
            error=f"Failed to set reminder: {str(e)}",
        )
