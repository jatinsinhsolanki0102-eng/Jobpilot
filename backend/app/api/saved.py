from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, SavedJob, User
from ..services.serializers import job_to_dict
from .deps import get_current_user

router = APIRouter(prefix="/saved", tags=["saved"])


@router.get("")
def list_saved(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    saved = list(
        db.scalars(
            select(SavedJob)
            .where(SavedJob.user_id == user.id)
            .order_by(SavedJob.created_at.desc())
        )
    )
    return [job_to_dict(s.job) for s in saved if s.job is not None]


@router.post("/{job_id}", status_code=status.HTTP_201_CREATED)
def save_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = db.scalar(
        select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id)
    )
    if existing is None:
        db.add(SavedJob(user_id=user.id, job_id=job_id))
        db.commit()
    return {"saved": True}


@router.delete("/{job_id}")
def unsave_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(
        select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id)
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return {"saved": False}
