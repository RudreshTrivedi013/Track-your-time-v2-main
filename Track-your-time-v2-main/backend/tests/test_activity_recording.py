from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.activity import ActivitySource, ActivityType, ReminderActivity
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services import activity_service
from app.services.companion.intent_parser import ParsedIntent
from app.services.companion.task_actions import execute_intent


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def first(self):
        return self.value


class FakeSession:
    def __init__(self, execute_value=None):
        self.added = []
        self.execute_value = execute_value

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def execute(self, statement):
        return FakeScalarResult(self.execute_value)


def make_task(**overrides) -> Task:
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Authentication API",
        "status": TaskStatus.pending,
        "last_action_client_ts": None,
    }
    defaults.update(overrides)
    return Task(**defaults)


@pytest.mark.asyncio
async def test_record_activity_adds_exactly_one_row_with_metadata():
    db = FakeSession()
    user_id = uuid4()
    task = make_task(user_id=user_id)

    activity = await activity_service.record_activity(
        db,
        user_id=user_id,
        task=task,
        activity_type=ActivityType.created,
        source=ActivitySource.task,
        optional_notes="Created from dashboard",
        metadata={"event": "task_created"},
        timestamp=datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),
    )

    assert db.added == [activity]
    assert isinstance(activity, ReminderActivity)
    assert activity.activity_type == ActivityType.created
    assert activity.source == ActivitySource.task
    assert activity.task_id == task.id
    assert activity.task_title == "Authentication API"
    assert activity.metadata_json == {"event": "task_created"}


@pytest.mark.asyncio
async def test_companion_block_task_records_exactly_one_activity():
    user = User(id=uuid4(), email="test@example.com")
    task = make_task(user_id=user.id, title="Authentication API")
    db = FakeSession(execute_value=task)

    recorded = await execute_intent(
        db,
        user,
        ParsedIntent(action="block_task", reply="Blocked.", task_name="Authentication"),
    )

    activities = [item for item in db.added if isinstance(item, ReminderActivity)]
    assert recorded is True
    assert task.status == TaskStatus.blocked
    assert len(activities) == 1
    assert activities[0].activity_type == ActivityType.blocked
    assert activities[0].source == ActivitySource.companion
