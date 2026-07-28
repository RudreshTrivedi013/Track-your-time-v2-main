from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """
        Accept the plain Postgres URL that hosting providers hand out and point
        it at the asyncpg driver.

        Railway's Postgres plugin exposes DATABASE_URL as
        `postgresql://user:pass@postgres.railway.internal:5432/railway`, but the
        FastAPI side runs on asyncpg and needs the `+asyncpg` suffix. Requiring
        that edit by hand meant either rewriting the value on every credential
        rotation, or pasting a stale copy — and getting it wrong produces a
        confusing "dialect not async" crash at startup.

        Normalising here means you can wire Railway's variable straight through
        as a reference (`${{Postgres.DATABASE_URL}}`) and it just works.
        `database.py` still derives the Celery sync URL by stripping `+asyncpg`,
        so both engines stay correct.

        Heroku-style `postgres://` is handled too; SQLAlchemy dropped support
        for that spelling.
        """
        if not v:
            return v
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        # Leave any explicitly chosen driver alone (e.g. +psycopg2, +aiosqlite).
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    TEST_DATABASE_URL: str = ""

    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240  # 4 hours — avoids logout on Railway cold starts
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # LLM providers
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENAI_API_KEY: str = ""
    VOICE_MODEL: str = "gpt-4o-mini"

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_SUB: str = "mailto:you@example.com"

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    GRACE_PERIOD_MINUTES: int = 5

    # How often to re-notify a due task the user has not acted on. Deliberately
    # NOT derived from Task.interval_minutes — that field means recurrence
    # ("run this every 30 minutes"), which is a different concept from
    # "you haven't answered me yet". Env-overridable so dev can set it to 1.
    REMINDER_REPEAT_MINUTES: int = 10
    # Shorter backoff when every push attempt failed, so a transient outage
    # doesn't cost the user a full repeat interval.
    REMINDER_RETRY_MINUTES: int = 2

    ENVIRONMENT: str = "development"

    # Layered config, highest precedence last:
    #
    #   1. .env        — shared/live defaults (Railway Postgres + Redis).
    #   2. .env.local   — YOUR machine's overrides (local Postgres + Redis).
    #                     Gitignored. Delete or rename it and the app falls
    #                     straight back to the live values in .env, with no
    #                     code change.
    #   3. real environment variables — always win over both. This is what
    #      Railway/Vercel inject, so deployments need no .env file at all.
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
