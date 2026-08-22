from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

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
        # Remotive's public API no longer honours the search/category/limit
        # query params (it returns the same ~20 latest listings no matter what),
        # so fetch the feed and filter locally against the query keywords.
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(API_URL)
                resp.raise_for_status()
                jobs = resp.json().get("jobs", [])
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Remotive request failed: %s", exc)
            return []

        tokens = [t for t in re.split(r"\W+", (query or "").lower()) if t]
        results: list[RawJob] = []
        for job in jobs:
            mapped = _map_job(job)
            if mapped is None:
                continue
            if tokens:
                haystack = " ".join(
                    filter(
                        None,
                        [
                            mapped.title,
                            mapped.company_name,
                            mapped.description or "",
                            " ".join(mapped.skills_required or []),
                            mapped.employment_type or "",
                        ]
                    )
                ).lower()
                if not any(t in haystack for t in tokens):
                    continue
            results.append(mapped)
        # Newest first so the freshest listings are pushed to users.
        results.sort(
            key=lambda j: j.posted_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return results[:limit]
