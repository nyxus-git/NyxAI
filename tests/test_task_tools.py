"""Tests for task tools."""
import os
import pytest
import aiosqlite
import asyncio

from tools.tasks.task_tools import add_task, list_tasks, complete_task
import tools.tasks.task_tools

# Override DB_PATH for tests
TEST_DB = "./data/test_tasks.db"
tools.tasks.task_tools.DB_PATH = TEST_DB

@pytest.fixture(autouse=True)
async def setup_test_db():
    # Setup test schema
    os.makedirs(os.path.dirname(TEST_DB), exist_ok=True)
    async with aiosqlite.connect(TEST_DB) as conn:
        await conn.execute("DROP TABLE IF EXISTS tasks")
        await conn.execute("""
            CREATE TABLE tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        await conn.commit()
    yield
    # Teardown
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_task_workflow():
    # 1. Add a task
    res1 = await add_task("Buy groceries")
    assert res1.success is True
    task_id = res1.data["id"]
    
    # 2. List tasks
    res2 = await list_tasks()
    assert res2.success is True
    assert res2.data["count"] == 1
    assert "Buy groceries" in res2.display_text
    
    # 3. Complete task
    res3 = await complete_task(task_id)
    assert res3.success is True
    
    # 4. List tasks again
    res4 = await list_tasks()
    assert res4.success is True
    assert res4.data["count"] == 0
