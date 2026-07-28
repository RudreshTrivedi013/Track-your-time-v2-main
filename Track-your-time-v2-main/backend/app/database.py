from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings


class Base(DeclarativeBase):
    pass


def _normalise_async_url(url: str) -> str:
    """
    Force the asyncpg driver onto the URL.

    Railway (and Heroku, Render, Fly…) expose Postgres as `postgresql://…` — and
    Heroku-style providers still emit the legacy `postgres://`. Handing either to
    create_async_engine picks the default synchronous psycopg2 driver and blows up
    at boot with "The asyncio extension requires an async driver".

    Normalising here means you can paste the provider's variable straight in
    (`DATABASE_URL=${{Postgres.DATABASE_URL}}`) with no hand-editing, which is one
    less thing to get wrong at 2am. An explicit `+asyncpg` is left untouched.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# Async engine — used by FastAPI endpoints.
#
# The pool settings are not cosmetic. Measured against the remote Railway proxy,
# a COLD connect (TCP + TLS + auth) cost 13.2 SECONDS while a warm query cost
# ~486ms. With SQLAlchemy's defaults (pool_size=5, no pre-ping, no recycle) a
# connection that the proxy had silently idled out was only discovered when a
# query failed, so that 13-second reconnect landed on a real user request.
#
#   pool_pre_ping  — validate a connection before handing it out, so a dead
#                    socket is replaced during checkout instead of mid-query.
#   pool_recycle   — proactively retire connections before any upstream idle
#                    timeout can kill them (30 min is comfortably under
#                    typical proxy/Postgres idle limits).
#   pool_size/overflow — 5 was too tight; overflow connections are created AND
#                    torn down per burst, paying a full handshake on the hot path.
#
# Note: asyncpg needs statement_cache_size=0 behind a *pgbouncer*-style pooler
# in transaction mode. Railway's proxy is a plain TCP passthrough, so prepared
# statements are fine and we leave the cache enabled — disabling it would slow
# down local Postgres for no reason.
ASYNC_DATABASE_URL = _normalise_async_url(settings.DATABASE_URL)

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Sync engine — used by Celery tasks (asyncpg cannot run inside asyncio.run())
# Converts postgresql+asyncpg:// -> postgresql+psycopg2://
_sync_url = ASYNC_DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
