from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, Job, Preference, Resume, SavedJob, User
from ..schemas import DashboardStats
from ..services.matching import rank_jobs
from ..services.serializers import job_to_dict, pref_to_dict
from .deps import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardStats:
    applied = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.user_id == user.id)
        )
        or 0
    )
    by_status: dict[str, int] = {}
    for status, count in db.execute(
        select(Application.status, func.count())
        .where(Application.user_id == user.id)
        .group_by(Application.status)
    ):
        by_status[str(status)] = int(count)
    saved = (
        db.scalar(
            select(func.count())
            .select_from(SavedJob)
            .where(SavedJob.user_id == user.id)
        )
        or 0
    )
    total_jobs = db.scalar(select(func.count()).select_from(Job)) or 0

    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    pref = db.query(Preference).filter(Preference.user_id == user.id).first()

    top_matches: list[dict] = []
    if resume is not None and resume.raw_text:
        jobs = list(db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)))
        ranked = rank_jobs(
            resume_text=resume.raw_text,
            resume_skills=resume.skills,
            pref=pref_to_dict(pref),
            jobs=[job_to_dict(j) for j in jobs],
        )
        applied_ids = set(
            db.scalars(
                select(Application.job_id).where(Application.user_id == user.id)
            ).all()
        )
        for j in ranked[:6]:
            if j["id"] in applied_ids:
                continue
            top_matches.append(
                {
                    "id": j["id"],
                    "title": j["title"],
                    "company_name": j["company_name"],
                    "location": j.get("location"),
                    "work_mode": j.get("work_mode"),
                    "salary_min": j.get("salary_min"),
                    "salary_max": j.get("salary_max"),
                    "rank_score": j["rank_score"],
                    "match_score": j["match"]["score"],
                    "matched_skills": j["match"]["matched_skills"],
                }
            )

    apps = list(
        db.scalars(
            select(Application)
            .where(Application.user_id == user.id)
            .order_by(Application.created_at.desc())
            .limit(5)
        )
    )
    recent_applications = []
    for a in apps:
        recent_applications.append(
            {
                "id": a.id,
                "job_id": a.job_id,
                "status": a.status,
                "job_title": a.job.title if a.job else None,
                "company_name": a.job.company_name if a.job else None,
                "created_at": a.created_at,
            }
        )

    skills_by_cat: dict[str, int] = {}
    if resume is not None:
        for s in resume.skills or []:
            cat = s.get("category", "Other")
            skills_by_cat[cat] = skills_by_cat.get(cat, 0) + 1

    return DashboardStats(
        total_jobs=total_jobs,
        applied=applied,
        pending=by_status.get("pending", 0),
        interviews=by_status.get("interview", 0),
        offers=by_status.get("offer", 0),
        rejected=by_status.get("rejected", 0),
        saved=saved,
        top_matches=top_matches,
        recent_applications=recent_applications,
        top_skills=[{"category": k, "count": v} for k, v in skills_by_cat.items()],
    )
