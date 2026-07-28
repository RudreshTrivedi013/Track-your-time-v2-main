"""
Redis-backed cache for the per-request user lookup.

`get_current_user` runs on every authenticated request and used to issue an
unconditional `SELECT users WHERE id = :id`. Redis is local (sub-millisecond)
while that query measured ~4ms against local Postgres and ~935ms against the
remote Railway proxy, so caching it removes a real round trip from 100% of
requests.

Two deliberate constraints:

* Only the scalar columns are cached. The `tasks` / `devices` relationships are
  NOT — a cached user is detached from the session and traversing a relationship
  on it would attempt lazy IO. An audit of `app/api/` confirmed every read path
  only ever touches `user.id`, `user.timezone` and `user.primary_device_id`.

* The TTL is short on purpose. Anything that edits a user row through the app
  invalidates the key explicitly (see `get_current_user_for_write`), but an
  out-of-band change made straight in the database would otherwise be invisible
  forever. 60 seconds bounds that staleness without meaningfully hurting the
  hit rate.
"""
import json
import logging
import uuid
from datetime import datetime, time

# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis

from app.config import settings
from app.models import User

logger = logging.getLogger(__name__)

USER_CACHE_TTL_SECONDS = 60

# Columns safe to round-trip through JSON. Deliberately excludes relationships.
_CACHED_COLUMNS = (
    "id",
    "email",
    "hashed_password",
    "timezone",
    "primary_device_id",
    "quiet_hours_start",
    "quiet_hours_end",
    "working_hours_start",
    "working_hours_end",
    "checkin_interval_minutes",
    "daily_summary_enabled",
    "reminders_enabled",
    "checkin_enabled",
    "created_at",
)

# One client (and therefore one connection pool) for the process. The previous
# get_redis() dependency built a fresh aioredis client per request and closed
# it, paying a new TCP connect every time.
_redis: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _key(user_id: uuid.UUID | str) -> str:
    return f"user:{user_id}"


def _encode(user: User) -> str:
    payload = {}
    for column in _CACHED_COLUMNS:
        value = getattr(user, column, None)
        if isinstance(value, uuid.UUID):
            # str(), NOT isoformat() — UUID has no isoformat. Note asyncpg hands
            # back its own asyncpg.pgproto.UUID, which subclasses uuid.UUID, so
            # this branch catches both.
            payload[column] = str(value)
        elif isinstance(value, (datetime, time)):
            payload[column] = value.isoformat()
        else:
            payload[column] = value
    return json.dumps(payload)


def _decode(raw: str) -> User:
    """Rebuild a DETACHED User. Never add this to a session."""
    data = json.loads(raw)
    user = User()
    for column, value in data.items():
        if value is None:
            setattr(user, column, None)
        elif column in ("id", "primary_device_id"):
            setattr(user, column, uuid.UUID(value))
        elif column == "created_at":
            setattr(user, column, datetime.fromisoformat(value))
        elif column in (
            "quiet_hours_start",
            "quiet_hours_end",
            "working_hours_start",
            "working_hours_end",
        ):
            setattr(user, column, time.fromisoformat(value))
        else:
            setattr(user, column, value)
    return user


async def get_cached_user(user_id: uuid.UUID) -> User | None:
    """Return the cached user, or None on a miss. Never raises."""
    try:
        raw = await get_redis_client().get(_key(user_id))
    except Exception as exc:
        # A Redis outage must not take authentication down with it — the caller
        # falls back to querying Postgres.
        logger.warning("[UserCache] read failed, falling back to DB: %s", exc)
        return None

    if not raw:
        return None
    try:
        return _decode(raw)
    except Exception as exc:
        logger.warning("[UserCache] malformed entry for %s, ignoring: %s", user_id, exc)
        return None


async def set_cached_user(user: User) -> None:
    try:
        await get_redis_client().set(_key(user.id), _encode(user), ex=USER_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("[UserCache] write failed for %s: %s", user.id, exc)


async def invalidate_cached_user(user_id: uuid.UUID) -> None:
    try:
        await get_redis_client().delete(_key(user_id))
    except Exception as exc:
        logger.warning("[UserCache] invalidate failed for %s: %s", user_id, exc)
