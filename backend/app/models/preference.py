from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin

if TYPE_CHECKING:
    from .user import User


class Preference(Base, TimestampMixin):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    job_type: Mapped[str | None] = mapped_column(String(30))
    work_modes: Mapped[list | None] = mapped_column(JSON)
    locations: Mapped[list | None] = mapped_column(JSON)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    experience_level: Mapped[str | None] = mapped_column(String(50))
    company_types: Mapped[list | None] = mapped_column(JSON)
    domains: Mapped[list | None] = mapped_column(JSON)
    include_broad_suggestions: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="preference")
