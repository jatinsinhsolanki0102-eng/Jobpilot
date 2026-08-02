import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Resume, User
from ..schemas import ResumeOut, UploadResponse
from ..services.resume_parser import parse_resume
from .deps import get_current_user

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


@router.post(
    "/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED
)
def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    ext = Path(file.filename or "").suffix.lower()
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

    size = 0
    chunk = file.file.read(1024 * 1024)
    chunks = [chunk]
    while chunk:
        chunk = file.file.read(1024 * 1024)
        chunks.append(chunk)
        size += len(chunk)
    if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit"
        )

    user_dir = Path(settings.UPLOAD_DIR) / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = user_dir / storage_name
    with storage_path.open("wb") as out:
        for c in chunks:
            if c:
                out.write(c)

    file_type = ALLOWED_EXTENSIONS[ext]
    resume = Resume(
        user_id=user.id,
        filename=file.filename or storage_name,
        storage_path=str(storage_path),
        file_type=file_type,
        parse_status="parsing",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    try:
        parsed = parse_resume(storage_path, file_type)
        data = parsed.as_dict()
        resume.raw_text = parsed.raw_text
        resume.skills = data.get("skills", [])
        resume.projects = data.get("projects", [])
        resume.experience = data.get("experience", [])
        resume.education = data.get("education", [])
        resume.certifications = data.get("certifications", [])
        resume.structured = data
        resume.parse_status = "parsed"
    except Exception as exc:  # noqa: BLE001
        resume.parse_status = "failed"
        resume.parse_error = str(exc)
    db.commit()
    db.refresh(resume)
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
    try:
        Path(resume.storage_path).unlink(missing_ok=True)
        parent = Path(resume.storage_path).parent
        if parent.is_dir() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)
    except OSError:
        pass
    db.delete(resume)
    db.commit()
