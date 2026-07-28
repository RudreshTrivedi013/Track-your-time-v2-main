"""
intent_parser.py — safely parses the LLM's JSON response.

Responsibilities
----------------
- Strip markdown fences that some models add despite being told not to.
- Parse JSON without crashing on any input.
- Validate field types and enum values.
- Return a safe ``ParsedIntent`` with defaults for every missing field.
- Log warnings for unexpected values so we can improve the prompt later.

This module NEVER raises an exception to the caller.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known action values — anything else falls back to "unknown"
# ---------------------------------------------------------------------------

KNOWN_ACTIONS = frozenset(
    [
        "chat_only",
        "set_current_task",
        "complete_task",
        "create_task",
        "update_task",
        "block_task",
        "resume_task",
        "list_tasks",
        "log_productivity",
        "unknown",
    ]
)

KNOWN_PRODUCTIVITY_STATUSES = frozenset(["focused", "distracted", "break", "idle"])


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ParsedIntent:
    """Normalised, validated representation of the LLM's structured response."""

    action: str = "unknown"
    reply: str = "I'm here to help! Could you rephrase that?"
    task_name: Optional[str] = None
    task_id: Optional[str] = None
    confidence: float = 0.0
    productivity_status: Optional[str] = None
    duration_minutes: Optional[int] = None
    note: Optional[str] = None
    raw_json: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that the model sometimes adds."""
    t = text.strip()
    # Handle ```json ... ``` or ``` ... ```
    if t.startswith("```"):
        parts = t.split("```")
        # parts[1] is the inner content (may start with 'json\n')
        inner = parts[1] if len(parts) > 1 else ""
        if inner.startswith("json"):
            inner = inner[4:]
        t = inner.strip()
    # Remove any stray trailing backticks
    return t.strip("`").strip()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        f = float(value)
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return default


def _safe_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_intent(raw_text: str) -> ParsedIntent:
    """
    Parse the LLM's raw text output into a safe ``ParsedIntent``.

    This function:
    1. Strips fences.
    2. Attempts JSON parse — returns safe fallback on failure.
    3. Validates action enum.
    4. Validates productivity_status enum.
    5. Clamps confidence to [0, 1].
    6. Attaches the raw dict for debugging.

    Never raises.
    """
    # --- Step 1: strip fences ------------------------------------------------
    cleaned = _strip_fences(raw_text)

    # --- Step 2: parse JSON --------------------------------------------------
    try:
        data: dict = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "intent_parser: JSON decode failed. raw=%r error=%s", raw_text[:200], exc
        )
        return ParsedIntent(
            action="unknown",
            reply=(
                "I had a little hiccup processing that — could you try again? "
                "I'm here to help!"
            ),
            raw_json={},
        )

    if not isinstance(data, dict):
        logger.warning("intent_parser: parsed JSON is not a dict: %r", data)
        return ParsedIntent(raw_json=data if isinstance(data, dict) else {})

    # --- Step 3: action -------------------------------------------------------
    raw_action = _safe_str(data.get("action")) or "unknown"
    if raw_action not in KNOWN_ACTIONS:
        logger.warning("intent_parser: unknown action %r, defaulting to chat_only", raw_action)
        raw_action = "chat_only"

    # --- Step 4: reply (always required) -------------------------------------
    raw_reply = _safe_str(data.get("reply"))
    if not raw_reply:
        logger.warning("intent_parser: missing 'reply' field in LLM response")
        raw_reply = "I'm here to help! Let me know what you need."

    # --- Step 5: productivity_status -----------------------------------------
    prod_status = _safe_str(data.get("productivity_status"))
    if prod_status and prod_status not in KNOWN_PRODUCTIVITY_STATUSES:
        logger.warning(
            "intent_parser: invalid productivity_status %r, clearing", prod_status
        )
        prod_status = None

    return ParsedIntent(
        action=raw_action,
        reply=raw_reply,
        task_name=_safe_str(data.get("task_name")),
        task_id=_safe_str(data.get("task_id")),
        confidence=_safe_float(data.get("confidence"), 0.5),
        productivity_status=prod_status,
        duration_minutes=_safe_int(data.get("duration_minutes")),
        note=_safe_str(data.get("note")),
        raw_json=data,
    )
