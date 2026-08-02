import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import NotificationSettings, TelegramLink, TelegramLinkCode, User
from ..services.pipeline import default_settings, run_user_scan
from ..services.telegram import bot
from .deps import get_current_user

router = APIRouter(prefix="/telegram", tags=["telegram"])
settings = get_settings()


class SettingsUpdate(BaseModel):
    notify_enabled: bool | None = None
    min_match_score: int | None = Field(default=None, ge=0, le=100)
    scheduler_interval_minutes: int | None = Field(default=None, ge=15, le=1440)
    search_keywords: list[str] | None = None
    max_per_scan: int | None = Field(default=None, ge=1, le=20)
    daily_summary_enabled: bool | None = None
    weekly_report_enabled: bool | None = None


@router.post("/link")
def create_link_code(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    code = secrets.token_hex(3).upper()
    record = TelegramLinkCode(user_id=user.id, code=code)
    db.add(record)
    db.commit()
    return {
        "code": code,
        "bot_username": settings.TELEGRAM_BOT_USERNAME,
        "bot_available": bot.available,
        "expires_in_minutes": 15,
    }


@router.get("/status")
def telegram_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    link = user.telegram_link
    ns = default_settings(db, user)
    db.commit()
    return {
        "linked": link is not None and link.enabled,
        "chat_id": link.chat_id if link else None,
        "username": link.username if link else None,
        "last_message_at": link.last_message_at if link else None,
        "bot_available": bot.available,
        "bot_username": settings.TELEGRAM_BOT_USERNAME,
        "settings": {
            "notify_enabled": ns.notify_enabled,
            "min_match_score": ns.min_match_score,
            "scheduler_interval_minutes": ns.scheduler_interval_minutes,
            "search_keywords": ns.search_keywords or [],
            "max_per_scan": ns.max_per_scan,
            "daily_summary_enabled": ns.daily_summary_enabled,
            "weekly_report_enabled": ns.weekly_report_enabled,
            "last_scan_at": ns.last_scan_at,
        },
    }


@router.put("/settings")
def update_settings(
    payload: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    ns = default_settings(db, user)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(ns, field, value)
    db.commit()
    return {
        "ok": True,
        "settings": {
            field: getattr(ns, field)
            for field in (
                "notify_enabled",
                "min_match_score",
                "scheduler_interval_minutes",
                "max_per_scan",
                "daily_summary_enabled",
                "weekly_report_enabled",
            )
        },
    }


@router.post("/sync-now")
def sync_now(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Trigger an immediate background scan for this user."""
    link = user.telegram_link
    ns = default_settings(db, user)
    db.commit()
    if link is None or not link.enabled:
        return {"error": "Link your Telegram account first"}
    if not bot.available:
        return {"error": "Telegram bot token not configured on the server"}
    return run_user_scan(user.id)
