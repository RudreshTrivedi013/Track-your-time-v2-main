"""
Web Push delivery as a background job.

Why this exists: `pywebpush` is a blocking HTTP client, and the API used to fire
it from inside request handlers via `loop.run_in_executor(...)` without awaiting
the returned future. That had three problems:

  1. The request first had to run its own `SELECT devices` to find where to send
     — a database round trip on the hot path of every task mutation, purely for
     work the user is not waiting on.
  2. Because the futures were never awaited, `GoneException` (HTTP 410 — the
     subscription was revoked) was silently swallowed. Stale devices were never
     deleted, so every future send retried a dead endpoint forever.
  3. The default ThreadPoolExecutor is shared and bounded. A burst of pushes
     could saturate it and stall unrelated executor work behind it.

Moving both the device lookup AND the send in here means the request does zero
extra database work, and the 410 cleanup finally happens.
"""
import logging

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models.notification_log import Device
from app.services.push_service import send_push, GoneException
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.push_tasks.send_push_to_user")
def send_push_to_user(user_id: str, payload: dict) -> dict:
    """
    Fan a single payload out to every push-capable device belonging to `user_id`.

    Devices with `push_enabled=False` or a NULL `push_token` are skipped: the
    first opted out, and the second has nothing to send to (`send_push` would
    fail on the None token anyway).

    A device whose subscription returns 410/404 is deleted here — that is the
    only place the cleanup happens now, so it must not be removed.
    """
    with SyncSessionLocal() as db:
        devices = db.execute(
            select(Device).where(
                Device.user_id == user_id,
                Device.push_enabled.is_(True),
                Device.push_token.is_not(None),
            )
        ).scalars().all()

        if not devices:
            logger.debug("[Push] No push-capable devices for user %s — nothing to send", user_id)
            return {"sent": 0, "removed": 0, "failed": 0}

        sent = removed = failed = 0
        for device in devices:
            try:
                if send_push(device.push_token, payload):
                    sent += 1
                else:
                    failed += 1
            except GoneException:
                # Subscription revoked — drop the device so we stop retrying it.
                logger.info("[Push] Device %s subscription gone — removing (user %s)", device.id, user_id)
                db.delete(device)
                removed += 1
            except Exception as exc:
                logger.warning("[Push] Send to device %s failed: %s", device.id, exc)
                failed += 1

        db.commit()

    logger.info(
        "[Push] type=%s user=%s sent=%d removed=%d failed=%d",
        payload.get("type", "?"), user_id, sent, removed, failed,
    )
    return {"sent": sent, "removed": removed, "failed": failed}
