from __future__ import annotations

import logging
import re

import httpx

from .base import JobSource, RawJob
from .common import dedupe_strs, parse_iso_datetime, parse_usd_salary

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_WS_RE = re.compile(r"\s+")

_JOB_TYPE_LABEL = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "contract": "Contract",
    "internship": "Internship",
    "freelance": "Freelance",
}


def _clean_html(text: str | None) -> str | None:
    if not text:
        return None
    out = _HTML_WS_RE.sub(" ", _HTML_TAG_RE.sub(" ", text))
    return out.strip() or None


def _map_job(job: dict) -> RawJob | None:
    title = (job.get("title") or "").strip()
    company = (job.get("company_name") or "").strip()
    if not title or not company:
        return None
    description = _clean_html(job.get("description"))
    salary = job.get("salary")
    salary_min, salary_max = parse_usd_salary(salary) if salary else (None, None)
    job_type = _JOB_TYPE_LABEL.get((job.get("job_type") or "").lower(), "Full-time")
    return RawJob(
        source_id=f"remotive:{job.get('id')}",
        source="remotive",
        title=title,
        company_name=company,
        location=job.get("candidate_required_location") or "Remote",
        work_mode="Remote",
        employment_type=job_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="USD",
        experience_required=None,
        description=description,
        skills_required=dedupe_strs(job.get("tags") or []),
        application_deadline=None,
        posted_at=parse_iso_datetime(job.get("publication_date")),
        url=job.get("url"),
    )


class RemotiveSource(JobSource):
    """Official Remotive remote-jobs API. Free, no auth required."""

    name = "remotive"

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
        pages: int = 1,
    ) -> list[RawJob]:
        params: dict = {"limit": min(max(limit, 1), 50)}
        if query:
            params["search"] = query
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                jobs = resp.json().get("jobs", [])
        except httpx.HTTPError as exc:
            logger.warning("Remotive request failed: %s", exc)
            return []

        results: list[RawJob] = []
        for job in jobs:
            mapped = _map_job(job)
            if mapped is None:
                continue
            results.append(mapped)
        return results[:limit]
