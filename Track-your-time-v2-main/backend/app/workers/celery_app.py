from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "reminder_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.reminder_tasks",
        "app.workers.summary_tasks",
        "app.workers.checkin_tasks",
        "app.workers.push_tasks",
    ],
)

from celery.signals import worker_process_init


@worker_process_init.connect
def configure_workers(*args, **kwargs):
    from app.database import engine, sync_engine

    # Dispose of any database connection pools inherited from the parent process
    engine.sync_engine.dispose()
    sync_engine.dispose()


import os

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Cap the prefork pool. Celery defaults to one child process per CPU core,
    # and cloud hosts report the HOST's core count, not the container's share —
    # on Railway that came back as 48. Forking 48 copies of this app (SQLAlchemy,
    # models, the Groq client) blows straight past the memory limit, so the
    # container was OOM-killed mid-boot and restart-looped every ~4 seconds,
    # never reaching "ready".
    #
    # Set here rather than as a `--concurrency` CLI flag so it cannot be lost
    # when a start command is edited. Override with CELERY_CONCURRENCY if a
    # genuinely heavier workload ever needs it.
    #
    # 2 is ample: this worker sends web-push HTTP calls and runs a handful of
    # scheduled jobs — it is IO-bound and low-volume, not CPU-bound.
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "2")),

    # Silences the startup warning and keeps 5.x behaviour explicit: retry the
    # broker connection during startup instead of dying if Redis is a moment
    # slower to come up than the worker.
    broker_connection_retry_on_startup=True,
)

import logging
_logger = logging.getLogger(__name__)
_logger.info("[Scheduler] Celery beat configured with %d schedules", len(celery_app.conf.beat_schedule or {}))

# Why server-driven scheduling (Celery, not client timers):
# Client timers (setTimeout / JS intervals) die the moment a tab closes, a
# phone sleeps, or the app is killed by the OS. A reminder app whose alarms
# stop working when the screen is off is useless. Celery beat runs
# independently of any client, on the server, so reminders fire reliably
# regardless of what any individual device is doing. The server is the single
# source of truth for "what time is it / what's due", which also sidesteps
# clock-skew bugs across devices.

# This MUST stay at 60s, and the old "Every 5 minutes" comment here was wrong.
#
# checkin_service.slot_start_utc only returns a slot when the current time is
# within _SCHEDULER_WINDOW_MINUTES (= 2) *after* a due slot:
#
#     minutes_since_due = elapsed_minutes % interval_minutes
#     if minutes_since_due >= _SCHEDULER_WINDOW_MINUTES: return None
#
# Ticking every 60s means minutes_since_due is always 0 or 1, so every slot is
# caught. Ticking every 5 minutes would sample at 0, 5, 10 … and any slot that
# came due 2-4 minutes after a tick would fall outside the window and be
# silently dropped — a check-in the user never gets. If you want a slower beat,
# widen _SCHEDULER_WINDOW_MINUTES to match it first.
checkin_schedule = 60.0
celery_app.conf.beat_schedule = {
    "check-due-reminders-every-60s": {
        "task": "app.workers.reminder_tasks.check_due_reminders",
        "schedule": 60.0,
    },

    "run-day-end-summaries-hourly": {
        # Runs hourly and internally filters to users whose local time is
        # currently 9pm, since users can be in any timezone.
        "task": "app.workers.summary_tasks.run_day_end_summaries",
        "schedule": crontab(minute=0),
    },

    "run-hourly-checkins": {
        "task": "app.workers.checkin_tasks.run_hourly_checkins",
        "schedule": checkin_schedule,
    },
}
