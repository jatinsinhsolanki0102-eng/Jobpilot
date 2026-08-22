from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Application, Job, Preference, Resume, User
from ..schemas import JobDetail, MatchBreakdown, RankedJob
from ..services.ai import generate_cover_letter
from ..services.job_sources import (
    SOURCE_LABELS,
    source_available,
    sync_source,
)
from ..services.job_sources.common import PLAYWRIGHT_AVAILABLE
from ..services.matching import ai_match_score, match_scores, rank_jobs
from ..services.serializers import job_to_dict, pref_to_dict
from .deps import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _source_availability(key: str) -> tuple[bool, str | None]:
    """Whether a source can actually run on this server, plus why not."""
    if key == "adzuna":
        s = get_settings()
        if not (s.ADZUNA_APP_ID and s.ADZUNA_APP_KEY):
            return False, "Needs ADZUNA_APP_ID / ADZUNA_APP_KEY on the server"
        return True, None
    if key == "remotive":
        return True, None
    # Browser-based scrapers need playwright
    if PLAYWRIGHT_AVAILABLE:
        return True, None
    return False, "Needs a headless browser (unavailable on this server)"


@router.get("", response_model=list[RankedJob])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    source: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RankedJob]:
    query = select(Job)
    if source:
        query = query.where(Job.source == source)
    jobs = list(db.scalars(query.order_by(Job.created_at.desc()).limit(200)))

    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    pref = db.query(Preference).filter(Preference.user_id == user.id).first()

    if resume is None or not resume.raw_text:
        ranked = [job_to_dict(j) for j in jobs]
        ranked.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
        return [RankedJob(**j) for j in ranked[:limit]]

    ranked = rank_jobs(
        resume_text=resume.raw_text,
        resume_skills=resume.skills,
        pref=pref_to_dict(pref),
        jobs=[job_to_dict(j) for j in jobs],
    )
    return [RankedJob(**j) for j in ranked[:limit]]


class SyncRequest(BaseModel):
    source: str = Field(default="internshala", max_length=40)
    query: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=80)
    internship: bool = True
    limit: int = Field(default=20, ge=1, le=50)
    with_details: bool = True


@router.post("/sync")
def sync_jobs(
    payload: SyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Scrape listings from a supported platform and upsert them locally."""
    if not source_available(payload.source):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown job source '{payload.source}'. "
                f"Supported: {', '.join(sorted(SOURCE_LABELS))}"
            ),
        )
    try:
        return sync_source(
            db=db,
            source=payload.source,
            query=payload.query or None,
            location=payload.location or None,
            internship=payload.internship,
            limit=payload.limit,
            with_details=payload.with_details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        label = SOURCE_LABELS.get(payload.source, payload.source)
        raise HTTPException(
            status_code=400,
            detail=f"{label} can't run on this server ({exc}). "
            "Try Remotive, or configure Adzuna API keys.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - never leak a CORS-less 500
        label = SOURCE_LABELS.get(payload.source, payload.source)
        raise HTTPException(
            status_code=502,
            detail=f"{label} sync failed: {exc.__class__.__name__}. Try again shortly.",
        ) from exc


@router.get("/sources")
def list_sources(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(select(Job.source, func.count(Job.id)).group_by(Job.source)).all()
    counts = {source: count for source, count in rows}
    known = []
    for key, label in sorted(SOURCE_LABELS.items()):
        available, reason = _source_availability(key)
        known.append(
            {
                "key": key,
                "label": label,
                "count": counts.get(key, 0),
                "available": available,
                "reason": reason,
            }
        )
    if counts:
        known.insert(0, {"key": "", "label": "All", "count": sum(counts.values()), "available": True, "reason": None})
    else:
        known.insert(0, {"key": "", "label": "All", "count": 0, "available": True, "reason": None})
    return known


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: int,
    with_ai: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobDetail:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    detail = JobDetail(**job_to_dict(job))
    has_applied = (
        db.scalar(
            select(Application.id).where(
                Application.user_id == user.id, Application.job_id == job_id
            )
        )
        is not None
    )
    detail.has_applied = has_applied

    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    if resume is not None and resume.raw_text:
        scores = match_scores(resume.raw_text, resume.skills, [job_to_dict(job)])
        detail.match = MatchBreakdown(**scores[job_id])
        if with_ai:
            detail.ai_assessment = ai_match_score(
                resume.raw_text, resume.skills, job_to_dict(job)
            )
    return detail


@router.post("/{job_id}/cover-letter")
def cover_letter(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    if resume is None:
        raise HTTPException(status_code=400, detail="Upload a resume first")

    letter = generate_cover_letter(
        candidate={
            "skills": resume.skills or [],
            "projects": resume.projects or [],
            "experience": resume.experience or [],
            "education": resume.education or [],
            "full_name": (resume.structured or {}).get("full_name") or user.full_name,
        },
        job=job_to_dict(job),
        company=job.company_name,
    )
    if letter is None:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured. Set GROQ_API_KEY to generate cover letters.",
        )
    return {"cover_letter": letter}
