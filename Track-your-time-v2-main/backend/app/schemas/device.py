from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeviceRegisterRequest(BaseModel):
    push_token: str  # JSON-encoded PushSubscription from the browser
    is_primary: bool = False


class DeviceOut(BaseModel):
    id: UUID
    is_primary: bool
    last_active_at: datetime
    push_enabled: bool

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    summary: str
    highlight: str
    concern: str
    tomorrow_suggestion: str
