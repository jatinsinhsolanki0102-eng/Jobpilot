import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal, get_db
from ..models import Resume, User
from ..schemas import ResumeOut, UploadResponse
from ..services.resume_parser import parse_resume
from .deps import get_current_user

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


def _run_parse(resume_id: int, data: bytes, file_type: str) -> None:
    """Parse a resume in the background so uploads return immediately."""
    db = SessionLocal()
    try:
        resume = db.get(Resume, resume_id)
        if resume is None:
            return
        try:
            parsed = parse_resume(data, file_type)
            structured = parsed.as_dict()
            resume.raw_text = parsed.raw_text
            resume.skills = structured.get("skills", [])
            resume.projects = structured.get("projects", [])
            resume.experience = structured.get("experience", [])
            resume.education = structured.get("education", [])
            resume.certifications = structured.get("certifications", [])
            resume.structured = structured
            resume.parse_status = "parsed"
        except Exception as exc:  # noqa: BLE001
            resume.parse_status = "failed"
            resume.parse_error = str(exc)
        db.commit()
    finally:
        db.close()


@router.post(
    "/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED
)
def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    filename = file.filename or ""
    ext = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Only PDF or TXT resumes are supported"
        )
    if (
        file.content_type
        and file.content_type not in ALLOWED_CONTENT_TYPES
        and ext != ".txt"
    ):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    data = file.file.read()
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit"
        )

    # No disk writes here on purpose: container filesystems (Belmo etc.)
    # may be read-only. The bytes are parsed in the background task and
    # only extracted text/structured data is persisted to the database.
    storage_name = f"{uuid.uuid4().hex}{ext}"

    file_type = ALLOWED_EXTENSIONS[ext]
    resume = Resume(
        user_id=user.id,
        filename=file.filename or storage_name,
        storage_path=f"memory/{user.id}/{storage_name}",
        file_type=file_type,
        parse_status="parsing",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    background_tasks.add_task(_run_parse, resume.id, data, file_type)
    return UploadResponse(resume=ResumeOut.model_validate(resume))


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Resume]:
    return list(
        db.scalars(
            select(Resume)
            .where(Resume.user_id == user.id)
            .order_by(Resume.created_at.desc())
        )
    )


@router.get("/latest", response_model=ResumeOut | None)
def latest_resume(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Resume | None:
    return db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status_code=404, detail="Resume not found")
    db.delete(resume)
    db.commit()
