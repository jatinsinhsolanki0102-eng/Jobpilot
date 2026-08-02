from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: str
    source: str
    title: str
    company_name: str
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str
    experience_required: str | None = None
    description: str | None = None
    skills_required: list | None = None
    benefits: list | None = None
    application_deadline: datetime | None = None
    posted_at: datetime | None = None
    url: str | None = None
    created_at: datetime


class MatchBreakdown(BaseModel):
    score: float
    skill_match: float
    semantic_match: float
    matched_skills: list[str]
    missing_skills: list[str]


class RankedJob(JobBase):
    match: MatchBreakdown | None = None
    preference_fit: float | None = None
    rank_score: float | None = None


class JobDetail(RankedJob):
    ai_assessment: dict[str, Any] | None = None
    has_applied: bool = False
