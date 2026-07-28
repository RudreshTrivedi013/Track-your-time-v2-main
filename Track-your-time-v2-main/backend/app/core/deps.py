from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.core.user_cache import (
    get_cached_user,
    get_redis_client,
    invalidate_cached_user,
    set_cached_user,
)
from app.database import get_db
from app.models import User

# auto_error=False so a MISSING Authorization header raises our own 401 rather
# than FastAPI's default 403. The frontend's refresh interceptor only reacts to
# 401, so a 403 here meant a dropped token silently failed with no recovery.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_redis() -> aioredis.Redis:
    """Yield the shared async Redis client.

    This used to build a brand-new `aioredis.from_url(...)` client — and with it
    a fresh connection pool — on every single request, then close it, paying a
    TCP connect each time. One client per process is what redis-py's pooling is
    designed for.
    """
    yield get_redis_client()


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _user_id_from_credentials(credentials: HTTPAuthorizationCredentials | None) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_exception()
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") not in ("access", "action"):
            raise _credentials_exception()
        return UUID(payload.get("sub"))
    except (ValueError, TypeError):
        raise _credentials_exception()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the caller, preferring the Redis cache over a database query.

    IMPORTANT: on a cache hit the returned User is **detached** from the SQLAlchemy
    session. That is fine for reading columns, which is all any read endpoint does,
    but it means you cannot mutate it and commit — SQLAlchemy is not tracking it and
    the change would be silently dropped. Endpoints that write to the user row must
    depend on `get_current_user_for_write` instead.
    """
    user_id = _user_id_from_credentials(credentials)

    cached = await get_cached_user(user_id)
    if cached is not None:
        return cached

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _credentials_exception()

    await set_cached_user(user)
    return user


async def get_current_user_for_write(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Same as `get_current_user`, but always loads from the database so the object
    is session-attached and therefore safe to mutate and commit.

    The cache entry is dropped *after* the response is sent (this is a generator
    dependency, so the code past the yield runs on the way out). Invalidating
    afterwards rather than before is what makes it correct: clearing the key up
    front would leave a window in which a concurrent request could re-populate it
    from the pre-write row.
    """
    user_id = _user_id_from_credentials(credentials)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _credentials_exception()

    try:
        yield user
    finally:
        await invalidate_cached_user(user_id)