from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from ..database import SessionLocal
from ..models import Application, Job, NotificationLog, ScanReport, TelegramLink, User
from .telegram import bot, format_daily_summary, format_weekly_report

logger = logging.getLogger(__name__)


def _merge_reports(reports: list[ScanReport]) -> dict:
    data = {
        "scanned": 0,
        "matched": 0,
        "sent": 0,
        "ignored": 0,
        "avg_score": 0.0,
        "best": {"title": "", "company": "", "score": 0},
    }
    best_score = 0
    for r in reports:
        d = r.data or {}
        for k in ("scanned", "matched", "sent", "ignored"):
            data[k] += d.get(k, 0)
        b = d.get("best") or {}
        if b.get("score", 0) > best_score:
            best_score = b["score"]
            data["best"] = {
                "title": b.get("title", ""),
                "company": b.get("company", ""),
                "score": b.get("score", 0),
            }
    matched = max(1, data["matched"])
    weighted = 0.0
    for r in reports:
        d = r.data or {}
        if d.get("matched"):
            weighted += d.get("avg_score", 0.0) * d["matched"]
    data["avg_score"] = round(weighted / matched, 1) if reports else 0.0
    return data


def daily_data(user_id: int) -> dict:
    db = SessionLocal()
    try:
        reports = list(
            db.scalars(
                select(ScanReport).where(
                    ScanReport.user_id == user_id,
                    ScanReport.period == "daily",
                    ScanReport.period_date == date.today().isoformat(),
                )
            )
        )
        return _merge_reports(reports)
    finally:
        db.close()


def weekly_data(user_id: int) -> dict:
    db = SessionLocal()
    try:
        since = (date.today() - timedelta(days=7)).isoformat()
        reports = list(
            db.scalars(
                select(ScanReport).where(
                    ScanReport.user_id == user_id,
                    ScanReport.period == "daily",
                    ScanReport.period_date >= since,
                )
            )
        )
        data = _merge_reports(reports)
        data["applications"] = (
            db.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.user_id == user_id)
            )
            or 0
        )
        data["interviews"] = (
            db.scalar(
                select(func.count())
                .select_from(Application)
                .where(
                    Application.user_id == user_id, Application.status == "interview"
                )
            )
            or 0
        )
        logs = db.scalars(
            select(NotificationLog).where(
                NotificationLog.user_id == user_id, NotificationLog.sent_at >= since
            )
        ).all()
        skills: Counter[str] = Counter()
        for log in logs:
            if log.job:
                for s in log.job.skills_required or []:
                    skills[str(s)] += 1
        data["top_skills"] = [s for s, _ in skills.most_common(8)]
        return data
    finally:
        db.close()


def _store_weekly(user_id: int, data: dict) -> None:
    from datetime import date

    db = SessionLocal()
    try:
        monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        existing = db.scalar(
            select(ScanReport).where(
                ScanReport.user_id == user_id,
                ScanReport.period == "weekly",
                ScanReport.period_date == monday,
            )
        )
        if existing is None:
            db.add(
                ScanReport(
                    user_id=user_id,
                    period="weekly",
                    period_date=monday,
                    data=data,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
    finally:
        db.close()


def send_daily_summaries() -> dict:
    if not bot.available:
        return {"skipped": "no_token"}
    sent = 0
    db = SessionLocal()
    try:
        links = list(
            db.scalars(select(TelegramLink).where(TelegramLink.enabled.is_(True)))
        )
        for link in links:
            user = db.get(User, link.user_id)
            if user is None or not user.is_active:
                continue
            ns = user.notification_settings
            if ns is not None and not ns.daily_summary_enabled:
                continue
            data = daily_data(user.id)
            if data.get("scanned", 0) == 0 and data.get("sent", 0) == 0:
                continue
            if bot.send_message(link.chat_id, format_daily_summary(data)):
                sent += 1
    finally:
        db.close()
    logger.info("Daily summaries sent: %d", sent)
    return {"sent": sent}


def send_weekly_reports() -> dict:
    if not bot.available:
        return {"skipped": "no_token"}
    sent = 0
    db = SessionLocal()
    try:
        links = list(
            db.scalars(select(TelegramLink).where(TelegramLink.enabled.is_(True)))
        )
        for link in links:
            user = db.get(User, link.user_id)
            if user is None or not user.is_active:
                continue
            ns = user.notification_settings
            if ns is not None and not ns.weekly_report_enabled:
                continue
            data = weekly_data(user.id)
            if data.get("scanned", 0) == 0:
                continue
            _store_weekly(user.id, data)
            if bot.send_message(link.chat_id, format_weekly_report(data)):
                sent += 1
    finally:
        db.close()
    logger.info("Weekly reports sent: %d", sent)
    return {"sent": sent}
