from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    parse_status: str
    parse_error: str | None = None
    raw_text: str | None = None
    skills: list[dict[str, str]] | None = None
    projects: list[dict[str, Any]] | None = None
    experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    certifications: list[str] | None = None
    structured: dict[str, Any] | None = None
    created_at: datetime


class UploadResponse(BaseModel):
    resume: ResumeOut
