from pydantic import BaseModel, field_validator


class VoiceTranscriptRequest(BaseModel):
    transcript: str


class ParsedNote(BaseModel):
    text: str


class ParsedTask(BaseModel):
    title: str
    due_date: str | None = None       # ISO date "YYYY-MM-DD" or relative descriptor, validated downstream
    due_time: str | None = None       # "HH:MM" 24h, may be None if ambiguous
    recurrence: str = "none"          # none|interval|daily|weekly
    interval_minutes: int | None = None
    notes: list[ParsedNote] = []
    ambiguous_fields: list[str] = []

    @field_validator("recurrence")
    @classmethod
    def validate_recurrence(cls, v: str) -> str:
        allowed = {"none", "interval", "daily", "weekly"}
        if v not in allowed:
            raise ValueError(f"recurrence must be one of {allowed}")
        return v


class ParsedVoiceResult(BaseModel):
    tasks: list[ParsedTask]
