from datetime import datetime, time, timezone
from uuid import uuid4

from app.models.user import User
from app.services.companion import checkin_service


class FakeResult:
    def __init__(self, count: int):
        self.count = count

    def scalar(self):
        return self.count


class FakeSession:
    def __init__(self, count: int = 0):
        self.count = count
        self.executed = False

    def execute(self, statement):
        self.executed = True
        return FakeResult(self.count)


def make_user(**overrides) -> User:
    defaults = dict(
        id=uuid4(),
        email="test@example.com",
        hashed_password="hash",
        timezone="UTC",
        working_hours_start=time(9, 0),
        working_hours_end=time(17, 0),
        quiet_hours_start=None,
        quiet_hours_end=None,
        checkin_interval_minutes=60,
        checkin_enabled=True,
    )
    defaults.update(overrides)
    return User(**defaults)


def test_30_minute_interval_is_due_only_on_interval_window():
    user = make_user(checkin_interval_minutes=30)
    due_db = FakeSession()

    assert checkin_service.sync_needs_checkin(
        due_db, user, datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    ) is True
    assert due_db.executed is True

    next_tick_db = FakeSession()
    assert checkin_service.sync_needs_checkin(
        next_tick_db, user, datetime(2026, 1, 1, 9, 35, tzinfo=timezone.utc)
    ) is False
    assert next_tick_db.executed is False


def test_5_minute_interval_is_due_on_each_scheduler_tick_without_logs():
    user = make_user(checkin_interval_minutes=5)

    for minute in (5, 10, 15):
        db = FakeSession()
        assert checkin_service.sync_needs_checkin(
            db, user, datetime(2026, 1, 1, 9, minute, tzinfo=timezone.utc)
        ) is True
        assert db.executed is True


def test_60_minute_interval_is_not_due_before_next_hour():
    user = make_user(checkin_interval_minutes=60)
    early_db = FakeSession()

    assert checkin_service.sync_needs_checkin(
        early_db, user, datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    ) is False
    assert early_db.executed is False

    due_db = FakeSession()
    assert checkin_service.sync_needs_checkin(
        due_db, user, datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    ) is True
    assert due_db.executed is True


def test_overnight_working_hours_are_respected():
    user = make_user(
        working_hours_start=time(22, 0),
        working_hours_end=time(6, 0),
        checkin_interval_minutes=60,
    )
    db = FakeSession()

    assert checkin_service.sync_needs_checkin(
        db, user, datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc)
    ) is True
    assert db.executed is True


def test_quiet_hours_skip_checkins():
    user = make_user(
        quiet_hours_start=time(12, 0),
        quiet_hours_end=time(13, 0),
        checkin_interval_minutes=60,
    )
    db = FakeSession()

    assert checkin_service.sync_needs_checkin(
        db, user, datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ) is False
    assert db.executed is False
