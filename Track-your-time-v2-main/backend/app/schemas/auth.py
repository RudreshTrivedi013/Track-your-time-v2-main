from datetime import time
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_timezone(value: str | None) -> str | None:
    """Reject unknown IANA zones at the edge.

    An unparseable timezone is not a cosmetic problem: the Celery beat loop
    calls ZoneInfo(user.timezone) for quiet-hours math, so one bad row used to
    raise mid-tick and abort reminder processing for every other user too.
    """
    if value is None:
        return None
    try:
        ZoneInfo(value)
    except Exception:
        raise ValueError(f"Unknown timezone: {value}")
    return value


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    timezone: str = "UTC"

    _check_timezone = field_validator("timezone")(_validate_timezone)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    timezone: str
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    working_hours_start: time
    working_hours_end: time
    checkin_interval_minutes: int
    daily_summary_enabled: bool
    reminders_enabled: bool
    checkin_enabled: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    working_hours_start: time | None = None
    working_hours_end: time | None = None
    checkin_interval_minutes: int | None = Field(None, ge=5, le=240)
    daily_summary_enabled: bool | None = None
    reminders_enabled: bool | None = None
    checkin_enabled: bool | None = None
    timezone: str | None = None

    _check_timezone = field_validator("timezone")(_validate_timezone)
