from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin

if TYPE_CHECKING:
    from .job import Job
    from .user import User


class NotificationSettings(Base, TimestampMixin):
    """Per-user rules for the background agent / Telegram notifications."""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_match_score: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    scheduler_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    search_keywords: Mapped[list | None] = mapped_column(JSON)
    max_per_scan: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    daily_summary_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    weekly_report_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="notification_settings")


class TelegramLink(Base, TimestampMixin):
    """Binds a Telegram chat to a JobPilot account."""

    __tablename__ = "telegram_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="telegram_link")


class TelegramLinkCode(Base, TimestampMixin):
    """One-time code shown on the web app that the user sends to the bot to link."""

    __tablename__ = "telegram_link_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(
        String(16), unique=True, index=True, nullable=False
    )
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class NotificationLog(Base, TimestampMixin):
    """Records every notification actually sent (used for dedup + analytics)."""

    __tablename__ = "notification_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "channel", name="uq_user_job_channel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="telegram")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="notification_logs")
    job: Mapped["Job | None"] = relationship(back_populates="notification_logs")


class ScanReport(Base, TimestampMixin):
    """Aggregated stats for daily / weekly analytics reports."""

    __tablename__ = "scan_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "period", "period_date", name="uq_user_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # daily | weekly
    period_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="scan_reports")
