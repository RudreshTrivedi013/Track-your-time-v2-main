"""
Lightweight keyword-based intent extractor for reminder response utterances.
Supports exactly five intents:
  1. started       — "Started frontend", "I began the task"
  2. working       — "I'm working on auth", "Debugging notifications"
  3. completed     — "Finished backend", "Completed login"
  4. blocked       — "I'm blocked because Docker won't start"
  5. status_update — catch-all for anything that doesn't match the above
No LLM / external calls — pure regex, deterministic, instantaneous.
"""
import re
from typing import NamedTuple
# ---------------------------------------------------------------------------
# Intent patterns (ordered from most specific to least specific)
# ---------------------------------------------------------------------------
# Each entry: (activity_type, list[compiled_regex])
_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "completed",
        [
            re.compile(
                r"\b(completed?|finished?|done|wrapped\s+up|delivered|shipped|closed)\b",
                re.IGNORECASE,
            )
        ],
    ),
    (
        "started",
        [
            re.compile(
                r"\b(started?|began|beginning|kicked\s+off|launched|picked\s+up|initiating|initiated)\b",
                re.IGNORECASE,
            )
        ],
    ),
    (
        "blocked",
        [
            re.compile(
                r"\b(blocked?|stuck|can'?t|cannot|issue|problem|won'?t\s+start|doesn'?t\s+work|error|failing|failed)\b",
                re.IGNORECASE,
            )
        ],
    ),
    (
        "working",
        [
            re.compile(
                r"\b(working\s+on|working|currently|debugging|implementing|building|investigating|reviewing|testing|fixing|handling)\b",
                re.IGNORECASE,
            )
        ],
    ),
]
# Filler words stripped when isolating the task title
_FILLER = re.compile(
    r"^(i'?m|i\s+am|i|the|a|an|on|for|with|that|it|this)\s+",
    re.IGNORECASE,
)
# Intent trigger words to strip from the beginning of the remaining text
# (so "started frontend" → title="frontend", not "started frontend")
_TRIGGER_STRIP = re.compile(
    r"^(completed?|finished?|done|wrapped\s+up|delivered|shipped|closed"
    r"|started?|began|beginning|kicked\s+off|launched|picked\s+up"
    r"|blocked?|stuck|working\s+on|working|currently|debugging"
    r"|implementing|building|investigating|reviewing|testing|fixing|handling"
    r"|initiating|initiated)\s*",
    re.IGNORECASE,
)
# Connecting words sometimes glued to a reason ("because", "since", "as")
_BECAUSE = re.compile(r"\b(because|since|as|due\s+to)\b", re.IGNORECASE)
class ExtractedIntent(NamedTuple):
    activity_type: str
    task_title: str
    optional_notes: str | None
def extract_intent(text: str) -> ExtractedIntent:
    """
    Parse a free-form reminder response utterance into a structured intent.
    Returns an ``ExtractedIntent`` namedtuple with:
      - ``activity_type`` — one of the five supported intent strings
      - ``task_title``    — best-effort extracted task/topic name
      - ``optional_notes`` — leftover text (blocker reason, extra detail), or None
    Algorithm
    ---------
    1. Scan the text against each pattern in order (completed > started >
       blocked > working > status_update).
    2. Once a match is found, trim the matched token and surrounding filler
       words to isolate the task title.
    3. For "blocked", split on "because/since/as" — everything before is the
       title, everything after is the blocker note.
    4. Fall back to activity_type="status_update" and task_title=cleaned text
       if no pattern fires.
    """
    stripped = text.strip()
    for activity_type, patterns in _PATTERNS:
        for pattern in patterns:
            if pattern.search(stripped):
                # Remove the matched trigger word + leading filler
                after = pattern.sub("", stripped, count=1).strip()
                after = _FILLER.sub("", after).strip()
                after = _TRIGGER_STRIP.sub("", after).strip()
                if activity_type == "blocked":
                    # Split on "because / since / as / due to" to get blocker note
                    split = _BECAUSE.split(after, maxsplit=1)
                    task_title = _clean_title(split[0])
                    optional_notes = split[-1].strip() if len(split) > 1 else None
                    # If we couldn't isolate a task title, use full text
                    if not task_title:
                        task_title = _clean_title(stripped)
                else:
                    task_title = _clean_title(after)
                    optional_notes = None
                return ExtractedIntent(
                    activity_type=activity_type,
                    task_title=task_title or _clean_title(stripped),
                    optional_notes=optional_notes if optional_notes else None,
                )
    # ── No pattern matched → status_update fallback ──
    return ExtractedIntent(
        activity_type="status_update",
        task_title=_clean_title(stripped),
        optional_notes=None,
    )
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_title(raw: str) -> str:
    """
    Strip punctuation from the end and normalise whitespace.
    Caps the result at 200 characters to stay well inside the DB column limit.
    """
    cleaned = raw.strip().rstrip(".,!?;:")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:200] if cleaned else "General Update"