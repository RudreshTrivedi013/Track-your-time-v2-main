"""
Unit tests for the reminder scheduling predicate and cursor bookkeeping.

These pin down the two bugs that made reminders unusable:

  1. A one-off task fired exactly TWICE (~60s apart) and then went silent
     forever, because the post-send code nulled next_due_at and the due_at
     fallback clause then matched on the very next tick.
  2. A recurring task pushed on EVERY 60s tick forever, because due_at was
     deliberately left set for recurring tasks so the same fallback matched
     endlessly — interval_minutes never entered the scheduling path at all.

Like test_task_service.py these run against in-memory Task objects with no
DB or network. Run with: pytest tests/test_reminder_repeat.py -v
"""
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.models.task import Task, TaskStatus, Recurrence
from app.models.user import User
from app.workers import reminder_tasks

REPEAT = timedelta(minutes=settings.REMINDER_REPEAT_MINUTES)
RETRY = timedelta(minutes=settings.REMINDER_RETRY_MINUTES)

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def make_task(**overrides) -> Task:
    defaults = dict(
        id=uuid4(),
        user_id=uuid4(),
        title="Test task",
        status=TaskStatus.pending,
        recurrence=Recurrence.none,
        due_at=None,
        anchor_time=None,
        interval_minutes=None,
        next_due_at=None,
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
    )
    defaults.update(overrides)
    return User(**defaults)


# ── Regression 1: the one-off double-fire ───────────────────────────────────


def test_one_off_does_not_double_fire_on_the_next_tick():
    task = make_task(due_at=T0, next_due_at=T0)

    assert reminder_tasks.is_due(task, T0) is True
    reminder_tasks.mark_notified(task, T0, sent=True)

    # The old code nulled next_due_at here, and due_at (still set) matched the
    # fallback clause 60 seconds later for a second, unwanted push.
    assert reminder_tasks.is_due(task, T0 + timedelta(seconds=60)) is False
    assert reminder_tasks.is_due(task, T0 + timedelta(minutes=5)) is False

    # ...but it must come back on the repeat cadence, not go silent forever.
    assert reminder_tasks.is_due(task, T0 + REPEAT) is True


def test_one_off_keeps_repeating_until_acted_on():
    task = make_task(due_at=T0, next_due_at=T0)

    now = T0
    for expected_count in range(1, 6):
        assert reminder_tasks.is_due(task, now) is True
        reminder_tasks.mark_notified(task, now, sent=True)
        assert task.notify_count == expected_count
        assert task.next_due_at > now  # cursor is always in the future
        now += REPEAT

    # Five reminders in and still going — this is "repeat until acted on".
    assert reminder_tasks.is_due(task, now) is True


# ── Regression 2: the recurring every-60s storm ─────────────────────────────


def test_recurring_interval_one_minute_does_not_nag_every_tick():
    task = make_task(
        recurrence=Recurrence.interval,
        interval_minutes=1,
        due_at=T0,
        anchor_time=T0,
        next_due_at=T0,
    )

    reminder_tasks.mark_notified(task, T0, sent=True)

    # The old code pushed on every single tick here because due_at stayed set.
    for minute in range(1, int(settings.REMINDER_REPEAT_MINUTES)):
        assert reminder_tasks.is_due(task, T0 + timedelta(minutes=minute)) is False

    assert reminder_tasks.is_due(task, T0 + REPEAT) is True


def test_due_at_alone_never_selects_a_task():
    """due_at is descriptive. Only next_due_at drives the scheduler."""
    task = make_task(due_at=T0 - timedelta(days=1), next_due_at=None)
    assert reminder_tasks.is_due(task, T0) is False


# ── Snooze ──────────────────────────────────────────────────────────────────


def test_active_snooze_suppresses_a_passed_next_due_at():
    task = make_task(
        status=TaskStatus.snoozed,
        next_due_at=T0 - timedelta(hours=1),          # long overdue
        snoozed_until=T0 + timedelta(minutes=30),     # but snoozed into the future
    )
    # Previously these were OR'd, so the passed cursor fired anyway and snooze
    # did not actually silence anything.
    assert reminder_tasks.is_due(task, T0) is False
    assert reminder_tasks.is_due(task, T0 + timedelta(minutes=31)) is True


def test_firing_a_snoozed_task_returns_it_to_pending():
    task = make_task(status=TaskStatus.snoozed, snoozed_until=T0)

    assert reminder_tasks.is_due(task, T0) is True
    reminder_tasks.mark_notified(task, T0, sent=True)

    assert task.status == TaskStatus.pending
    assert task.snoozed_until is None


# ── Mute ────────────────────────────────────────────────────────────────────


def test_blocked_task_is_never_due():
    """`blocked` is surfaced as Mute — the escape hatch must actually hold."""
    task = make_task(status=TaskStatus.blocked, next_due_at=T0 - timedelta(days=7))
    assert reminder_tasks.is_due(task, T0) is False


def test_done_task_is_never_due():
    task = make_task(status=TaskStatus.done, next_due_at=T0 - timedelta(days=7))
    assert reminder_tasks.is_due(task, T0) is False


# ── Deferral and failure paths ──────────────────────────────────────────────


def test_defer_does_not_count_as_a_notification():
    task = make_task(next_due_at=T0)
    later = T0 + timedelta(hours=8)

    reminder_tasks.defer_to(task, later)

    assert task.next_due_at == later
    assert task.notify_count == 0
    assert task.last_notified_at is None


def test_defer_clears_an_elapsed_snooze_instead_of_extending_it():
    task = make_task(snoozed_until=T0 - timedelta(minutes=5), next_due_at=T0)
    later = T0 + timedelta(hours=8)

    reminder_tasks.defer_to(task, later)

    assert task.snoozed_until is None
    assert task.next_due_at == later


def test_failed_send_uses_short_backoff_and_does_not_count():
    task = make_task(next_due_at=T0)

    reminder_tasks.mark_notified(task, T0, sent=False)

    assert task.notify_count == 0
    assert task.last_notified_at is None
    assert task.next_due_at == T0 + RETRY


# ── Quiet hours ─────────────────────────────────────────────────────────────


def test_quiet_hours_wrapping_midnight_defers_without_counting():
    user = make_user(
        timezone="UTC",
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(7, 0),
    )
    at_2am = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)

    is_quiet, push_to = reminder_tasks._in_quiet_hours(user, at_2am)
    assert is_quiet is True
    assert push_to == datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc)

    task = make_task(next_due_at=at_2am)
    reminder_tasks.defer_to(task, push_to)
    assert task.next_due_at == push_to
    assert task.notify_count == 0


def test_quiet_hours_outside_window_is_not_quiet():
    user = make_user(quiet_hours_start=time(22, 0), quiet_hours_end=time(7, 0))
    at_noon = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert reminder_tasks._in_quiet_hours(user, at_noon) == (False, None)


def test_corrupt_timezone_degrades_instead_of_raising():
    """One bad row used to abort the whole beat tick mid-loop."""
    user = make_user(
        timezone="Not/AZone",
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(7, 0),
    )
    assert reminder_tasks._in_quiet_hours(user, T0) == (False, None)
