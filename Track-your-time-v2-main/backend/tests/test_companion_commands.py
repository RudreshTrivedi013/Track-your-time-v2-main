import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.services.companion.intent_parser import parse_intent, ParsedIntent
from app.services.companion.task_actions import execute_intent
from app.services.companion.prompt_builder import build_system_prompt
from app.services.companion.context_builder import CompanionContext

_UTC = timezone.utc

def test_intent_parsing_new_actions():
    raw_json_update = '{"action":"update_task","reply":"Sure","task_name":"New Title"}'
    intent = parse_intent(raw_json_update)
    assert intent.action == "update_task"
    assert intent.task_name == "New Title"

    raw_json_block = '{"action":"block_task","reply":"Blocked","task_name":"Task"}'
    intent = parse_intent(raw_json_block)
    assert intent.action == "block_task"

    raw_json_resume = '{"action":"resume_task","reply":"Resumed","task_name":"Task"}'
    intent = parse_intent(raw_json_resume)
    assert intent.action == "resume_task"

@pytest.mark.asyncio
async def test_execute_update_task():
    db = AsyncMock()
    user = User(id=uuid.uuid4(), email="test@test.com")
    t_id = uuid.uuid4()
    
    # Mock finding the task
    task = Task(id=t_id, user_id=user.id, title="Old Title", status=TaskStatus.pending, last_action_client_ts=None)
    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = task
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = task
    res_mock.scalars.return_value = scalars_mock
    db.execute.return_value = res_mock

    intent = ParsedIntent(
        action="update_task",
        reply="Updated.",
        task_name="New Title",
        task_id=str(t_id)
    )

    await execute_intent(db, user, intent)
    assert task.title == "New Title"

@pytest.mark.asyncio
async def test_execute_block_task():
    db = AsyncMock()
    user = User(id=uuid.uuid4(), email="test@test.com")
    t_id = uuid.uuid4()
    
    task = Task(id=t_id, user_id=user.id, title="My Task", status=TaskStatus.pending, last_action_client_ts=None)
    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = task
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = task
    res_mock.scalars.return_value = scalars_mock
    db.execute.return_value = res_mock

    intent = ParsedIntent(
        action="block_task",
        reply="Blocked.",
        task_name="My Task"
    )

    await execute_intent(db, user, intent)
    assert task.status == TaskStatus.blocked

@pytest.mark.asyncio
async def test_execute_resume_task():
    db = AsyncMock()
    user = User(id=uuid.uuid4(), email="test@test.com")
    t_id = uuid.uuid4()
    
    task = Task(id=t_id, user_id=user.id, title="My Task", status=TaskStatus.blocked, last_action_client_ts=None)
    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = task
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = task
    res_mock.scalars.return_value = scalars_mock
    db.execute.return_value = res_mock

    intent = ParsedIntent(
        action="resume_task",
        reply="Resumed.",
        task_name="My Task"
    )

    await execute_intent(db, user, intent)
    assert task.status == TaskStatus.pending

def test_prompt_builder_includes_new_actions():
    ctx = CompanionContext(
        user_id=uuid.uuid4(),
        now_utc=datetime.now(timezone.utc).isoformat(),
        user_email="test@test.com",
        current_task=None,
        pending_tasks=[],
        completed_today=[],
        productivity_logs_today=[],
        recent_chat=[],
    )
    prompt = build_system_prompt(ctx)
    assert "update_task" in prompt
    assert "block_task" in prompt
    assert "resume_task" in prompt
