from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: str | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    status: str | None = Field(
        default=None, pattern="^(applied|pending|interview|rejected|offer|withdrawn)$"
    )
    cover_letter: str | None = None
    notes: str | None = None
    interview_date: datetime | None = None
    offer_details: dict[str, Any] | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    status: str
    cover_letter: str | None = None
    notes: str | None = None
    match_score: int | None = None
    interview_date: datetime | None = None
    offer_details: dict[str, Any] | None = None
    created_at: datetime
    job_title: str | None = None
    company_name: str | None = None
