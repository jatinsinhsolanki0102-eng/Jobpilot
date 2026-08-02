from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PreferenceBase(BaseModel):
    job_type: str | None = None
    work_modes: list[str] | None = None
    locations: list[str] | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    experience_level: str | None = None
    company_types: list[str] | None = None
    domains: list[str] | None = None
    include_broad_suggestions: bool = False


class PreferenceUpdate(PreferenceBase):
    pass


class PreferenceOut(PreferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    updated_at: datetime
