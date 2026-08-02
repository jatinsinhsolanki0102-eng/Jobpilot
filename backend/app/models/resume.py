from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin

if TYPE_CHECKING:
    from .user import User


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")

    raw_text: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    parse_error: Mapped[str | None] = mapped_column(Text)

    skills: Mapped[list | None] = mapped_column(JSON)
    projects: Mapped[list | None] = mapped_column(JSON)
    experience: Mapped[list | None] = mapped_column(JSON)
    education: Mapped[list | None] = mapped_column(JSON)
    certifications: Mapped[list | None] = mapped_column(JSON)
    structured: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped["User"] = relationship(back_populates="resumes")
