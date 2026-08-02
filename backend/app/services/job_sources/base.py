from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RawJob(BaseModel):
    """A job listing as extracted from an external source, pre-normalization."""

    source_id: str
    source: str = "internshala"
    title: str
    company_name: str
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "INR"
    experience_required: str | None = None
    description: str | None = None
    skills_required: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    application_deadline: datetime | None = None
    posted_at: datetime | None = None
    url: str | None = None


class JobSource:
    """Interface for job source scrapers."""

    name = "base"

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
    ) -> list[RawJob]:
        raise NotImplementedError
