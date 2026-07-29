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
    """New narrative-bullet summary shape.

    - generated_bullets: the AI-produced bullets (always present)
    - edited_bullets: the user's manual edits (null until the user edits)
    - is_edited: convenience flag — True when edited_bullets is not None
    """
    generated_bullets: list[str]
    edited_bullets: list[str] | None = None
    is_edited: bool = False
