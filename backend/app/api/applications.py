from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, Job, User
from ..schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate
from .deps import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])

STATUSES = {"applied", "pending", "interview", "rejected", "offer", "withdrawn"}


def _to_out(app: Application) -> ApplicationOut:
    out = ApplicationOut.model_validate(app)
    out.job_title = app.job.title if app.job else None
    out.company_name = app.job.company_name if app.job else None
    return out


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = db.scalar(
        select(Application).where(
            Application.user_id == user.id, Application.job_id == payload.job_id
        )
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="You have already applied to this job"
        )

    app = Application(
        user_id=user.id,
        job_id=payload.job_id,
        cover_letter=payload.cover_letter,
        notes=payload.notes,
        status="pending",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _to_out(app)


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    query = select(Application).where(Application.user_id == user.id)
    if status_filter:
        query = query.where(Application.status == status_filter)
    apps = list(db.scalars(query.order_by(Application.created_at.desc())))
    return [_to_out(a) for a in apps]


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    app = db.get(Application, application_id)
    if app is None or app.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status")
    for key, value in data.items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)
    return _to_out(app)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    app = db.get(Application, application_id)
    if app is None or app.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(app)
    db.commit()
