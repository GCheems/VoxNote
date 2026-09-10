from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal["uploaded", "transcribing", "completed", "summarizing", "failed"]


class SummaryRequest(BaseModel):
    api_key: str | None = Field(default=None, repr=False)
    base_url: str | None = None
    model: str | None = None
    language: str = "zh-CN"
    extra_instruction: str = ""


class Segment(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker: str = "Speaker 0"
    text: str

    @property
    def start(self) -> str:
        return format_timestamp(self.start_ms)

    @property
    def end(self) -> str:
        return format_timestamp(self.end_ms)


class Transcript(BaseModel):
    job_id: str
    filename: str
    engine: dict[str, Any]
    segments: list[Segment]
    created_at: str


class JobRecord(BaseModel):
    job_id: str
    filename: str
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    error: str | None = None
    created_at: str
    updated_at: str
    transcript_available: bool = False
    summary_available: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_timestamp(milliseconds: int, separator: str = ".") -> str:
    milliseconds = max(0, int(milliseconds))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"
