"""
Unit tests for the task state machine (scheduling math + idempotency).
These exercise app/services/task_service.py directly with in-memory Task
objects — no DB/network needed, matching the "test database, not dev
database" guidance while keeping these specific tests fast and isolated.

Run with: pytest tests/test_task_service.py -v
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.task import Task, TaskStatus, Recurrence
from app.services import task_service


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


def test_idempotent_done_action_is_noop_on_replay():
    task = make_task(status=TaskStatus.pending)
    ts = datetime.now(timezone.utc)

    changed_first = task_service.apply_action(task, "done", ts)
    assert changed_first is True
    assert task.status == TaskStatus.done

    # Replaying the exact same action/timestamp must be a no-op.
    changed_second = task_service.apply_action(task, "done", ts)
    assert changed_second is False
    assert task.status == TaskStatus.done  # unchanged


def test_idempotent_out_of_order_older_action_ignored():
    task = make_task(status=TaskStatus.pending)
    now = datetime.now(timezone.utc)
    newer_ts = now
    older_ts = now - timedelta(minutes=5)

    task_service.apply_action(task, "done", newer_ts)
    assert task.status == TaskStatus.done

    # An older action arriving late (out-of-order delivery) must not revert state.
    changed = task_service.apply_action(task, "reopen", older_ts)
    assert changed is False
    assert task.status == TaskStatus.done


def test_snooze_does_not_drift_unless_within_merge_window():
    anchor = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(
        recurrence=Recurrence.daily,
        anchor_time=anchor,
        next_due_at=anchor,
    )
    original_next_due = task.next_due_at

    # Snooze far away from next_due_at (e.g. 2 hours later) -> next_due_at untouched.
    client_ts = anchor
    task_service.apply_action(task, "snooze", client_ts, snooze_minutes=120)

    assert task.next_due_at == original_next_due
    assert task.snoozed_until == client_ts + timedelta(minutes=120)
    assert task.status == TaskStatus.snoozed


def test_snooze_merges_when_within_window_of_next_due_at():
    anchor = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(
        recurrence=Recurrence.daily,
        anchor_time=anchor,
        next_due_at=anchor,
    )
    client_ts = anchor - timedelta(minutes=10)

    # Snooze by 15 min -> lands at anchor + 5min, well within the 20-min merge window.
    task_service.apply_action(task, "snooze", client_ts, snooze_minutes=15)

    assert task.snoozed_until == client_ts + timedelta(minutes=15)
    # Merged: next_due_at should now equal the snoozed_until, not the original anchor.
    assert task.next_due_at == task.snoozed_until


def test_recurring_done_resets_to_pending_and_advances_from_anchor_not_now():
    anchor = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(
        recurrence=Recurrence.daily,
        anchor_time=anchor,
        next_due_at=anchor,
        status=TaskStatus.pending,
    )

    # Complete it "late" (well after the due time) to prove drift doesn't occur.
    completion_ts = anchor + timedelta(hours=5)
    task_service.apply_action(task, "done", completion_ts)

    assert task.status == TaskStatus.pending  # recurring tasks reset, not "done"
    # Next occurrence must be anchor + 1 day, NOT completion_ts + 1 day.
    assert task.next_due_at == anchor + timedelta(days=1)


def test_recurring_interval_advance_skips_missed_occurrences_from_anchor():
    anchor = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(
        recurrence=Recurrence.interval,
        interval_minutes=30,
        anchor_time=anchor,
        next_due_at=anchor,
    )

    # Complete it 95 minutes after anchor (so 3 intervals have already passed).
    completion_ts = anchor + timedelta(minutes=95)
    task_service.apply_action(task, "done", completion_ts)

    # 95 / 30 = 3 full intervals passed -> next occurrence is the 4th: anchor + 120min
    assert task.next_due_at == anchor + timedelta(minutes=120)


def test_non_recurring_done_goes_to_done_status():
    task = make_task(recurrence=Recurrence.none, status=TaskStatus.pending)
    task_service.apply_action(task, "done", datetime.now(timezone.utc))
    assert task.status == TaskStatus.done


def test_invalid_action_raises():
    task = make_task()
    with pytest.raises(task_service.InvalidAction):
        task_service.apply_action(task, "not_a_real_action", datetime.now(timezone.utc))


# ── Repeat-until-acknowledged bookkeeping ───────────────────────────────────


def test_done_on_recurring_resets_notify_state_and_uses_anchor():
    """A nagged task must reclaim its true cadence, not keep the nag cursor."""
    anchor = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(
        recurrence=Recurrence.daily,
        anchor_time=anchor,
        next_due_at=anchor + timedelta(minutes=30),  # a nag cursor
        notify_count=3,
        last_notified_at=anchor + timedelta(minutes=20),
    )

    task_service.apply_action(task, "done", anchor + timedelta(minutes=35))

    assert task.next_due_at == anchor + timedelta(days=1)
    assert task.notify_count == 0
    assert task.last_notified_at is None


def test_done_on_non_recurring_clears_the_cursor():
    task = make_task(recurrence=Recurrence.none, next_due_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc))
    task_service.apply_action(task, "done", datetime(2026, 1, 1, 9, 5, tzinfo=timezone.utc))

    assert task.status == TaskStatus.done
    assert task.next_due_at is None


def test_snooze_while_nagging_replaces_the_nag_cursor():
    """While nagging, next_due_at is a repeat cursor — not a real occurrence.

    Merging into it would be meaningless, and because the 10-minute nag cadence
    sits inside the 20-minute merge window it would otherwise fire constantly.
    """
    now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(
        recurrence=Recurrence.daily,
        anchor_time=now,
        next_due_at=now + timedelta(minutes=10),  # nag cursor
        notify_count=1,
    )

    task_service.apply_action(task, "snooze", now, snooze_minutes=60)

    assert task.snoozed_until == now + timedelta(minutes=60)
    # Replaced outright, despite 60 min being far outside the merge window.
    assert task.next_due_at == task.snoozed_until
    assert task.notify_count == 0


def test_block_resets_notify_state_and_clears_both_cursors():
    now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(next_due_at=now, snoozed_until=now, notify_count=5)

    task_service.apply_action(task, "block", now)

    assert task.status == TaskStatus.blocked
    assert task.next_due_at is None
    assert task.snoozed_until is None
    assert task.notify_count == 0


def test_reopen_past_due_non_recurring_does_not_immediately_renag():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    task = make_task(
        status=TaskStatus.done,
        recurrence=Recurrence.none,
        due_at=now - timedelta(days=1),   # already past
        next_due_at=now - timedelta(days=1),
    )

    task_service.apply_action(task, "reopen", now)

    assert task.status == TaskStatus.pending
    # Reopening a stale task means "I know about it" — don't buzz instantly.
    assert task.next_due_at is None


def test_reopen_future_due_non_recurring_rearms_the_cursor():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    future = now + timedelta(hours=3)
    task = make_task(status=TaskStatus.done, recurrence=Recurrence.none, due_at=future)

    task_service.apply_action(task, "reopen", now)

    assert task.next_due_at == future


def test_start_does_not_reset_notify_state():
    """Starting work is not an acknowledgement — keep nagging until done/muted."""
    now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    task = make_task(notify_count=2, last_notified_at=now)

    task_service.apply_action(task, "start", now)

    assert task.status == TaskStatus.in_progress
    assert task.notify_count == 2
