from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Company, Job
from .adzuna import AdzunaSource
from .base import JobSource, RawJob
from .internshala import InternshalaSource
from .linkedin import LinkedInSource
from .naukri import NaukriSource
from .remotive import RemotiveSource
from .unstop import UnstopSource
from .wellfound import WellfoundSource

logger = logging.getLogger(__name__)

SOURCE_CLASSES: dict[str, type[JobSource]] = {
    "internshala": InternshalaSource,
    "adzuna": AdzunaSource,
    "remotive": RemotiveSource,
    "linkedin": LinkedInSource,
    "wellfound": WellfoundSource,
    "naukri": NaukriSource,
    "unstop": UnstopSource,
}

SOURCE_LABELS: dict[str, str] = {
    "internshala": "Internshala",
    "adzuna": "Adzuna",
    "remotive": "Remotive",
    "linkedin": "LinkedIn",
    "wellfound": "Wellfound",
    "naukri": "Naukri",
    "unstop": "Unstop",
}


def source_available(source: str) -> bool:
    return source in SOURCE_CLASSES


def _apply_fields(job: Job, raw: RawJob) -> None:
    job.source_id = raw.source_id
    job.source = raw.source
    job.title = raw.title
    job.company_name = raw.company_name
    job.location = raw.location
    job.work_mode = raw.work_mode
    job.employment_type = raw.employment_type
    job.salary_min = raw.salary_min
    job.salary_max = raw.salary_max
    job.salary_currency = raw.salary_currency
    job.experience_required = raw.experience_required
    job.description = raw.description
    job.skills_required = raw.skills_required or []
    job.benefits = raw.benefits or []
    job.application_deadline = raw.application_deadline
    job.posted_at = raw.posted_at
    job.url = raw.url


def upsert_raw_jobs(db: Session, raw_jobs: list[RawJob]) -> dict:
    """Upsert scraped listings by source_id. Returns added/updated counts."""
    added = updated = 0
    for raw in raw_jobs:
        company = db.scalar(select(Company).where(Company.name == raw.company_name))
        if company is None:
            company = Company(name=raw.company_name)
            db.add(company)
            db.flush()

        existing = db.scalar(select(Job).where(Job.source_id == raw.source_id))
        if existing is not None:
            _apply_fields(existing, raw)
            existing.company_id = company.id
            updated += 1
        else:
            job = Job(source_id=raw.source_id, company_id=company.id)
            _apply_fields(job, raw)
            db.add(job)
            added += 1
    db.commit()
    return {"added": added, "updated": updated}


def sync_source(
    db: Session,
    source: str,
    query: str | None = None,
    location: str | None = None,
    internship: bool = True,
    limit: int = 20,
    with_details: bool = True,
    **kwargs,
) -> dict:
    """Scrape a given source and upsert listings. Raises ValueError for unknown sources."""
    cls = SOURCE_CLASSES.get(source)
    if cls is None:
        raise ValueError(
            f"Unknown job source '{source}'. "
            f"Available: {', '.join(sorted(SOURCE_CLASSES))}"
        )
    scraper = cls()
    raw_jobs = scraper.scrape(
        query=query,
        location=location,
        internship=internship,
        limit=limit,
        with_details=with_details,
        **kwargs,
    )
    failed = 0
    for raw in raw_jobs:
        if not raw.title or not raw.company_name:
            failed += 1
    valid = [r for r in raw_jobs if r.title and r.company_name]
    counts = upsert_raw_jobs(db, valid)
    return {
        "source": source,
        "source_label": SOURCE_LABELS.get(source, source),
        "total_found": len(raw_jobs),
        "added": counts["added"],
        "updated": counts["updated"],
        "failed": failed,
    }


def sync_internshala(
    db: Session,
    query: str | None = None,
    location: str | None = None,
    internship: bool = True,
    limit: int = 20,
    with_details: bool = True,
) -> dict:
    return sync_source(
        db,
        source="internshala",
        query=query,
        location=location,
        internship=internship,
        limit=limit,
        with_details=with_details,
    )
