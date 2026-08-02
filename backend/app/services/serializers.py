from __future__ import annotations

from datetime import datetime

from ..models import Job, Preference


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source_id": job.source_id,
        "source": job.source,
        "title": job.title,
        "company_name": job.company_name,
        "location": job.location,
        "work_mode": job.work_mode,
        "employment_type": job.employment_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "experience_required": job.experience_required,
        "description": job.description,
        "skills_required": job.skills_required or [],
        "benefits": job.benefits or [],
        "application_deadline": job.application_deadline,
        "posted_at": job.posted_at,
        "url": job.url,
        "created_at": job.created_at,
    }


def pref_to_dict(pref: Preference | None) -> dict | None:
    if pref is None:
        return None
    return {
        "job_type": pref.job_type,
        "work_modes": pref.work_modes or [],
        "locations": pref.locations or [],
        "salary_min": pref.salary_min,
        "salary_max": pref.salary_max,
        "experience_level": pref.experience_level,
        "company_types": pref.company_types or [],
        "domains": pref.domains or [],
        "include_broad_suggestions": pref.include_broad_suggestions,
    }


def utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
