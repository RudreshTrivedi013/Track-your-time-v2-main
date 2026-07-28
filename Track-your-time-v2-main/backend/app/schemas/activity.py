"""
Pydantic schemas for reminder activity submission and response.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class ActivitySubmitRequest(BaseModel):
    """
    Sent by the frontend when the user submits a reminder response (voice or text).
    ``text``    — the raw utterance, already transcribed if voice input was used.
    ``source``  — how the text was entered: "voice" (Web Speech API) or "text" (typed).
    ``task_id`` — optional UUID of the task the user is responding about.
                  The UI may pre-fill this from the notification context.
    """
    text: str = Field(..., min_length=1, max_length=2000)
    source: Literal["voice", "text"]
    task_id: UUID | None = Field(default=None)


class ActivityOut(BaseModel):
    """
    The persisted activity record returned after a successful submission.
    """
    id: UUID
    user_id: UUID
    task_id: UUID | None
    activity_type: str
    task_title: str
    optional_notes: str | None
    source: str
    timestamp: datetime
    metadata: dict | None = Field(
        default=None,
        validation_alias="metadata_json",
        serialization_alias="metadata",
    )

    model_config = {"from_attributes": True}
