"""
Tests for the beat loop orchestration in app/workers/reminder_tasks.py.

Uses a hand-rolled fake sync Session (matching the FakeSession style in
test_activity_recording.py) because the models use the Postgres UUID type,
which create_all() cannot emit on SQLite.

Run with: pytest tests/test_reminder_scheduler_loop.py -v
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.notification_log import Device, NotificationLog
from app.models.task import Task, TaskStatus, Recurrence
from app.models.user import User
from app.services import push_service
from app.services.push_service import GoneException
from app.workers import reminder_tasks

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


class FakeQuery:
    """Minimal stand-in for Session.query(Model) supporting the two shapes the
    scheduler uses: .filter(...).all() and .filter(...).first()."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, tasks=None, users=None, devices=None):
        self._by_model = {
            Task: tasks or [],
            User: users or [],
            Device: devices or [],
        }
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model):
        return FakeQuery(self._by_model.get(model, []))

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_task(**overrides) -> Task:
    defaults = dict(
        id=uuid4(),
        user_id=uuid4(),
        title="Test task",
        status=TaskStatus.pending,
        recurrence=Recurrence.none,
        due_at=T0,
        anchor_time=None,
        interval_minutes=None,
        next_due_at=T0,
        snoozed_until=None,
        snoozed_count_today=0,
        snoozed_count_total=0,
        last_action_client_ts=None,
        last_notified_at=None,
        notify_count=0,
    )
    defaults.update(overrides)
    return Task(**defaults)


def make_user(**overrides) -> User:
    defaults = dict(
        id=uuid4(),
        email="t@example.com",
        hashed_password="x",
        timezone="UTC",
        quiet_hours_start=None,
        quiet_hours_end=None,
        reminders_enabled=True,
    )
    defaults.update(overrides)
    return User(**defaults)


def make_device(user_id, **overrides) -> Device:
    defaults = dict(
        id=uuid4(),
        user_id=user_id,
        push_token='{"endpoint":"https://example.test/x"}',
        push_enabled=True,
    )
    defaults.update(overrides)
    return Device(**defaults)


@pytest.fixture
def sent(monkeypatch):
    """Capture push_service.send_push calls; return the recorded list."""
    calls = []

    def fake_send(token, payload):
        calls.append((token, payload))
        return True

    monkeypatch.setattr(push_service, "send_push", fake_send)
    return calls


def test_sends_to_every_enabled_device_and_logs_each(sent):
    user = make_user()
    task = make_task(user_id=user.id)
    devices = [make_device(user.id), make_device(user.id)]
    db = FakeSession(tasks=[task], users=[user], devices=devices)

    reminder_tasks._process_one(db, task, T0)

    assert len(sent) == 2
    logs = [o for o in db.added if isinstance(o, NotificationLog)]
    assert len(logs) == 2
    assert task.notify_count == 1
    assert task.next_due_at > T0


def test_gone_subscription_is_deleted(monkeypatch):
    user = make_user()
    task = make_task(user_id=user.id)
    device = make_device(user.id)
    db = FakeSession(tasks=[task], users=[user], devices=[device])

    def fake_send(token, payload):
        raise GoneException("expired")

    monkeypatch.setattr(push_service, "send_push", fake_send)
    reminder_tasks._process_one(db, task, T0)

    assert db.deleted == [device]
    # Nothing reached the user, so this is a short backoff, not a reminder.
    assert task.notify_count == 0


def test_no_devices_backs_off_instead_of_rescanning_forever(sent):
    user = make_user()
    task = make_task(user_id=user.id)
    db = FakeSession(tasks=[task], users=[user], devices=[])

    reminder_tasks._process_one(db, task, T0)

    assert sent == []
    assert task.notify_count == 0
    # The old code `continue`d without moving the cursor, so this task was
    # re-selected and re-examined on every single 60s tick, forever.
    assert task.next_due_at is not None and task.next_due_at > T0


def test_reminders_disabled_defers_without_notifying(sent):
    user = make_user(reminders_enabled=False)
    task = make_task(user_id=user.id)
    db = FakeSession(tasks=[task], users=[user], devices=[make_device(user.id)])

    reminder_tasks._process_one(db, task, T0)

    assert sent == []
    assert task.notify_count == 0
    assert task.next_due_at > T0


def test_one_failing_task_does_not_block_the_rest(monkeypatch, sent):
    user = make_user()
    bad = make_task(user_id=user.id, title="bad")
    good = make_task(user_id=user.id, title="good")
    db = FakeSession(tasks=[bad, good], users=[user], devices=[make_device(user.id)])

    real_process = reminder_tasks._process_one

    def flaky(session, task, now):
        if task.title == "bad":
            raise RuntimeError("boom")
        return real_process(session, task, now)

    monkeypatch.setattr(reminder_tasks, "_process_one", flaky)
    reminder_tasks._check_due_reminders_sync(session_factory=lambda: db)

    # The good task still went out, and the failure was isolated to its own
    # transaction. A single commit for the whole tick used to roll back every
    # task's bookkeeping *after* their pushes had already been delivered.
    assert len(sent) == 1
    assert db.rollbacks == 1
    assert db.commits == 1
    assert good.notify_count == 1
