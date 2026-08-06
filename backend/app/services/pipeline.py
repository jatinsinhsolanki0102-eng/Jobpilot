from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import (
    Job,
    Notification,
    NotificationLog,
    NotificationSettings,
    Preference,
    Resume,
    ScanReport,
    TelegramLink,
    User,
)
from .job_sources import SOURCE_CLASSES, upsert_raw_jobs
from .matching import rank_jobs
from .serializers import job_to_dict, pref_to_dict
from .telegram import bot, format_job_alert

logger = logging.getLogger(__name__)
settings = get_settings()

# Only push internships/jobs posted within this many days (latest opportunities).
# User preference: include postings from the last 1 week.
FRESH_DAYS = 7
# How many listings to scrape per scan (2 pages) so enough fresh jobs exist.
SCAN_LIMIT = 40
SCAN_PAGES = 2


def _posted_dt(job: dict) -> datetime | None:
    """Normalize a job's posted_at (falling back to created_at) to aware datetime."""
    posted = job.get("posted_at") or job.get("created_at")
    if not posted:
        return None
    if isinstance(posted, str):
        try:
            posted = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        except ValueError:
            return None
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return posted


def is_fresh(job: dict, days: int = FRESH_DAYS) -> bool:
    posted = _posted_dt(job)
    if posted is None:
        return False
    return (datetime.now(timezone.utc) - posted) <= timedelta(days=days)


def default_settings(db: Session, user: User) -> NotificationSettings:
    ns = user.notification_settings
    if ns is None:
        ns = NotificationSettings(user_id=user.id)
        db.add(ns)
        db.flush()
    return ns


def derive_keywords(
    user: User, ns: NotificationSettings, resume: Resume | None
) -> list[str]:
    if ns.search_keywords:
        return ns.search_keywords
    pref = user.preference
    if pref and pref.domains:
        return list(pref.domains)
    if resume and resume.skills:
        return [s["name"] for s in resume.skills[:3]]
    return ["python"]


def _passes_filters(
    job: dict, match: dict, ns: NotificationSettings, pref: Preference | None
) -> tuple[bool, str | None]:
    if match.get("score", 0) < ns.min_match_score:
        return False, "low_score"

    deadline = job.get("application_deadline")
    if deadline is not None:
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(
                    deadline.replace("Z", "+00:00")
                ).date()
            except ValueError:
                deadline = None
        if deadline is not None and deadline < date.today():
            return False, "expired"

    if pref:
        if (
            pref.salary_min
            and job.get("salary_min")
            and job["salary_min"] < pref.salary_min
        ):
            return False, "salary"
        if pref.locations:
            loc = (job.get("location") or "").lower()
            remote = (job.get("work_mode") or "").lower() == "remote"
            overlap = any(l.lower() in loc for l in pref.locations)
            if not overlap and not remote:
                return False, "location"
        if pref.work_modes:
            job_mode = (job.get("work_mode") or "").lower()
            allowed = [w.lower() for w in pref.work_modes]
            if job_mode and job_mode != "onsite" and job_mode not in allowed:
                return False, "work_mode"
    return True, None


def _log_sent(
    db: Session, user_id: int, job_id: int, channel: str = "telegram"
) -> None:
    """Record (or refresh) that a job was pushed. Re-sends update the timestamp
    instead of violating the (user_id, job_id, channel) unique key."""
    existing = db.scalar(
        select(NotificationLog).where(
            NotificationLog.user_id == user_id,
            NotificationLog.job_id == job_id,
            NotificationLog.channel == channel,
        )
    )
    if existing is not None:
        existing.sent_at = datetime.now(timezone.utc)
        return
    db.add(
        NotificationLog(
            user_id=user_id,
            job_id=job_id,
            channel=channel,
            sent_at=datetime.now(timezone.utc),
        )
    )


def _record_scan(db: Session, user_id: int, data: dict) -> None:
    today = date.today().isoformat()
    report = db.scalar(
        select(ScanReport).where(
            ScanReport.user_id == user_id,
            ScanReport.period == "daily",
            ScanReport.period_date == today,
        )
    )
    if report is None:
        report = ScanReport(
            user_id=user_id,
            period="daily",
            period_date=today,
            data={
                "scanned": 0,
                "matched": 0,
                "sent": 0,
                "ignored": 0,
                "avg_score": 0.0,
                "best": {},
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(report)
    d = dict(report.data or {})
    d["scanned"] = d.get("scanned", 0) + data.get("scanned", 0)
    d["matched"] = d.get("matched", 0) + data.get("matched", 0)
    d["sent"] = d.get("sent", 0) + data.get("sent", 0)
    d["ignored"] = d.get("ignored", 0) + data.get("ignored", 0)
    prev_avg = d.get("avg_score", 0.0) or 0.0
    prev_n = max(1, d["matched"] - data.get("matched", 0))
    d["avg_score"] = round(
        (prev_avg * prev_n + data.get("avg_score", 0.0) * data.get("matched", 0))
        / max(1, d["matched"]),
        1,
    )
    prev_best = d.get("best") or {}
    if data.get("best_score", 0) >= prev_best.get("score", 0):
        d["best"] = {
            "title": data.get("best_title", ""),
            "company": data.get("best_company", ""),
            "score": data.get("best_score", 0),
        }
    report.data = d
    db.commit()


def run_user_scan(user_id: int) -> dict:
    """Full background scan for one user: scrape -> match -> filter -> notify -> log."""
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return {"user_id": user_id, "skipped": "inactive"}
        link = user.telegram_link
        if link is None or not link.enabled:
            return {"user_id": user_id, "skipped": "not_linked"}
        ns = default_settings(db, user)
        if not ns.notify_enabled:
            return {"user_id": user_id, "skipped": "disabled"}

        resume = db.scalar(
            select(Resume)
            .where(Resume.user_id == user.id)
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
        if resume is None or not resume.raw_text:
            return {"user_id": user_id, "skipped": "no_resume"}
        pref = user.preference

        keywords = derive_keywords(user, ns, resume)
        query = keywords[0]
        logger.info("Scan for user %s (keyword=%s)", user_id, query)

        all_raw: list = []
        for name, cls in SOURCE_CLASSES.items():
            try:
                batch = cls().scrape(
                    query=query,
                    internship=True,
                    limit=SCAN_LIMIT,
                    pages=SCAN_PAGES,
                    with_details=True,
                )
                logger.info(
                    "Scraped source=%s for user %s: %d listings",
                    name,
                    user_id,
                    len(batch),
                )
                all_raw.extend(batch)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Scrape failed for source=%s user=%s: %s", name, user_id, exc
                )
        upsert_raw_jobs(db, all_raw)
        source_ids = {r.source_id for r in all_raw}
        if not source_ids:
            # Reset the cadence so a transient scrape failure doesn't cause a
            # re-scan on the very next scheduler tick.
            ns.last_scan_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "user_id": user_id,
                "scanned": 0,
                "sent": 0,
                "matched": 0,
                "skipped": "no_listings",
            }

        job_dicts = [
            job_to_dict(j)
            for j in db.scalars(select(Job).where(Job.source_id.in_(source_ids)))
        ]
        # Only the latest listings (posted within the last FRESH_DAYS days).
        fresh = [d for d in job_dicts if is_fresh(d, FRESH_DAYS)]

        if not fresh:
            # Reset the cadence so an empty fresh pool doesn't re-scan on the
            # very next scheduler tick.
            ns.last_scan_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "user_id": user_id,
                "scanned": len(job_dicts),
                "sent": 0,
                "matched": 0,
                "skipped": "no_fresh",
            }
        ranked = rank_jobs(
            resume_text=resume.raw_text,
            resume_skills=resume.skills,
            pref=pref_to_dict(pref),
            jobs=fresh,
        )
        # Newest postings win ties so the latest opportunities get pushed first.
        ranked.sort(
            key=lambda x: (
                x["rank_score"],
                _posted_dt(x) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        matched_count = sum(
            1 for j in ranked if j["match"]["score"] >= ns.min_match_score
        )
        sent = 0
        ignored = 0
        best_score = 0.0
        best_title = best_company = ""
        score_sum = 0.0

        for j in ranked:
            match = j["match"]
            if match["score"] >= ns.min_match_score:
                score_sum += match["score"]
            if match["score"] > best_score:
                best_score = match["score"]
                best_title = j["title"]
                best_company = j["company_name"]
            ok, reason = _passes_filters(j, match, ns, pref)
            if not ok:
                ignored += 1
                continue
            if sent >= ns.max_per_scan:
                ignored += 1
                continue

            msg = format_job_alert(j, match)
            if not bot.available:
                break
            if bot.send_message(link.chat_id, msg):
                db.add(
                    Notification(
                        user_id=user.id,
                        job_id=j["id"],
                        kind="new_match",
                        title=f"{j['title']} @ {j['company_name']}",
                        body=f"{match['score']:.0f}% match · {j.get('location') or 'Remote'}",
                    )
                )
                _log_sent(db, user.id, j["id"])
                sent += 1

        link.last_message_at = datetime.now(timezone.utc)
        ns.last_scan_at = datetime.now(timezone.utc)

        avg = round(score_sum / max(1, matched_count), 1) if matched_count else 0.0
        _record_scan(
            db,
            user.id,
            {
                "scanned": len(ranked),
                "matched": matched_count,
                "sent": sent,
                "ignored": ignored,
                "avg_score": avg,
                "best_title": best_title,
                "best_company": best_company,
                "best_score": best_score,
            },
        )
        db.commit()
        logger.info("Scan user %s: scanned=%d sent=%d", user_id, len(ranked), sent)
        return {
            "user_id": user_id,
            "scanned": len(ranked),
            "matched": matched_count,
            "sent": sent,
            "ignored": ignored,
            "avg_score": avg,
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Scan failed for user %s: %s", user_id, exc)
        return {"user_id": user_id, "error": str(exc)}
    finally:
        db.close()


def users_due_for_scan(db: Session, now: datetime) -> list[User]:
    users: list[User] = []
    for ns in db.scalars(select(NotificationSettings)):
        if not ns.notify_enabled:
            continue
        link = db.scalar(select(TelegramLink).where(TelegramLink.user_id == ns.user_id))
        if link is None or not link.enabled:
            continue
        last = ns.last_scan_at
        interval = max(15, ns.scheduler_interval_minutes)
        if last is None:
            user = db.get(User, ns.user_id)
            if user is not None:
                users.append(user)
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last) >= timedelta(minutes=interval):
            user = db.get(User, ns.user_id)
            if user is not None:
                users.append(user)
    return users


def sync_pass_all() -> dict:
    """Called by the scheduler: run a scan for every user due for one."""
    if not bot.available:
        logger.warning("Telegram not configured; skipping scheduled scan pass")
        return {"skipped": "no_token"}
    db = SessionLocal()
    try:
        due = users_due_for_scan(db, datetime.now(timezone.utc))
        user_ids = [u.id for u in due]
    finally:
        db.close()
    results = []
    for uid in user_ids:
        results.append(run_user_scan(uid))
    logger.info("Sync pass finished for %d users", len(user_ids))
    return {"users": results}
