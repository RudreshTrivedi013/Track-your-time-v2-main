"""
Web Push wrapper around pywebpush. Device targeting and quiet-hours logic
live in workers/reminder_tasks.py; this module just knows how to send.
"""
import json
import logging

from pywebpush import webpush, WebPushException

from app.config import settings

logger = logging.getLogger(__name__)


class GoneException(Exception):
    """Raised when a push subscription returns HTTP 410 Gone (expired/unsubscribed)."""


def send_push(push_token_json: str, payload: dict) -> bool:
    """push_token_json is the JSON-encoded PushSubscription stored on Device.

    Returns True on success, False on non-fatal errors.
    Raises GoneException if the subscription is expired (HTTP 410) — callers
    should delete the device record so it is never retried.
    """
    try:
        subscription_info = json.loads(push_token_json)
    except json.JSONDecodeError:
        logger.error("Invalid push_token JSON on device")
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIMS_SUB},
            ttl=86400,
        )
        endpoint = subscription_info.get("endpoint", "unknown")[:60]
        logger.info("[Push] Sent OK → endpoint=%s type=%s", endpoint, payload.get("type", "?"))
        return True
    except WebPushException as e:
        status_code = e.response.status_code if hasattr(e, "response") and e.response is not None else None
        body = e.response.text if hasattr(e, "response") and hasattr(e.response, "text") else "No response body"
        if status_code in (404, 410):
            # Subscription has been unsubscribed or expired — caller must delete the record.
            raise GoneException(f"Subscription gone ({status_code}): {body}") from e
        logger.warning(f"Push failed: {e}\nResponse body: {body}")
        return False


def build_reminder_payload(task_id: str, title: str, due_at_iso: str, user_id: str = None) -> dict:
    payload = {
        "type": "reminder",
        "tag": f"task-{task_id}",
        "task_id": task_id,
        "title": title,
        "due_at": due_at_iso,
    }
    if user_id:
        from app.core.security import create_action_token
        payload["action_token"] = create_action_token(user_id)
    return payload


def build_cancel_payload(task_id: str) -> dict:
    """Silent push telling other devices to dismiss a notification by tag."""
    return {
        "type": "cancel",
        "tag": f"task-{task_id}",
        "task_id": task_id,
        "silent": True,
    }


def build_summary_ready_payload(summary: dict) -> dict:
    """Build a push payload that includes the full summary so the OS notification
    body shows meaningful text without requiring the user to open the app.

    The 'body' field is used by the service worker to populate the OS notification body.
    The full 'summary' dict is embedded so the app can display the drawer contents
    immediately after tapping without an extra API call.
    """
    # Construct a concise notification body from the summary fields.
    body_parts = []
    if summary.get("highlight"):
        body_parts.append(f"✨ {summary['highlight']}")
    if summary.get("concern"):
        body_parts.append(f"⚠️ {summary['concern']}")
    body = " • ".join(body_parts) if body_parts else summary.get("summary", "Your day-end summary is ready.")

    return {
        "type": "summary_ready",
        "tag": "day-end-summary",
        "title": "Day-End Summary",
        "body": body,
        "summary": summary,
    }
