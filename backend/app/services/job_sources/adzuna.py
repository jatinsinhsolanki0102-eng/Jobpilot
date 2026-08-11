from __future__ import annotations

import logging
import re

import httpx

from ...config import get_settings
from .common import dedupe_strs, parse_iso_datetime, parse_work_mode
from .base import JobSource, RawJob

logger = logging.getLogger(__name__)

API_URL = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"

# Sanitize HTML so descriptions remain useful for TF-IDF matching.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_WS_RE = re.compile(r"\s+")


def _clean_html(text: str | None) -> str | None:
    if not text:
        return None
    out = _HTML_WS_RE.sub(" ", _HTML_TAG_RE.sub(" ", text))
    return out.strip() or None


def _parse_salary(result: dict) -> tuple[int | None, int | None]:
    lo = result.get("salary_min")
    hi = result.get("salary_max")
    return round(lo) if isinstance(lo, (int, float)) else None, (
        round(hi) if isinstance(hi, (int, float)) else None
    )


def _employment_type(result: dict) -> str | None:
    kind = (result.get("contract_type") or "").lower()
    time = (result.get("contract_time") or "").lower()
    if "part" in time:
        return "Part-time"
    if "internship" in kind or "internship" in (result.get("title") or "").lower():
        return "Internship"
    if "contract" in kind or "temporary" in kind:
        return "Contract"
    return "Full-time"


def _map_job(result: dict) -> RawJob | None:
    title = (result.get("title") or "").strip()
    company = ((result.get("company") or {}).get("display_name") or "").strip()
    if not title or not company:
        return None
    location = (result.get("location") or {}).get("display_name") or None
    description = _clean_html(result.get("description"))
    salary_min, salary_max = _parse_salary(result)
    salary_currency = result.get("salary_currency") or "INR"
    employment_type = _employment_type(result)
    return RawJob(
        source_id=f"adzuna:{result.get('id')}",
        source="adzuna",
        title=title,
        company_name=company,
        location=location,
        work_mode=parse_work_mode(
            " ".join(
                filter(
                    None,
                    [location or "", description or "", result.get("title") or ""],
                )
            )
        ),
        employment_type=employment_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        experience_required=None,
        description=description,
        skills_required=dedupe_strs((result.get("category") or {}).get("label") or []),
        application_deadline=None,
        posted_at=parse_iso_datetime(result.get("created")),
        url=result.get("redirect_url") or result.get("url"),
    )


class AdzunaSource(JobSource):
    """Official Adzuna India API. Needs ADZUNA_APP_ID / ADZUNA_APP_KEY in .env."""

    name = "adzuna"

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
        pages: int = 1,
    ) -> list[RawJob]:
        settings = get_settings()
        if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
            logger.warning(
                "Adzuna skipped: ADZUNA_APP_ID / ADZUNA_APP_KEY not configured"
            )
            return []
        results: list[RawJob] = []
        with httpx.Client(timeout=30) as client:
            for page in range(1, max(1, pages) + 1):
                params = {
                    "app_id": settings.ADZUNA_APP_ID,
                    "app_key": settings.ADZUNA_APP_KEY,
                    "results_per_page": min(limit, 50),
                    "content-type": "application/json",
                }
                if query:
                    params["what"] = f"{query} internship" if internship else query
                if location:
                    params["where"] = location
                # NOTE: Adzuna India does NOT accept employment_type=internship
                # (it returns HTTP 400 and kills the whole source). Instead we
                # append "internship" to the keyword search so real internships
                # flow in for student users (see _employment_type too).
                try:
                    resp = client.get(API_URL.format(page=page), params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Adzuna request failed: %s", exc)
                    break
                items = resp.json().get("results", [])
                for item in items:
                    job = _map_job(item)
                    if job is not None:
                        results.append(job)
                if not items or len(results) >= limit or page >= max(1, pages):
                    break
        return results[:limit]
