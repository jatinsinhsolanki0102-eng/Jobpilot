from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, Job, NotificationLog, SavedJob, ScanReport, User
from .deps import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(
    days: int = 14,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    daily = {
        r.period_date: (r.data or {})
        for r in db.scalars(
            select(ScanReport).where(
                ScanReport.user_id == user.id,
                ScanReport.period == "daily",
                ScanReport.period_date >= since,
            )
        )
    }
    app_counts: Counter = Counter()
    for created_at in db.scalars(
        select(Application.created_at).where(
            Application.user_id == user.id,
            Application.created_at
            >= datetime.combine(
                date.today() - timedelta(days=days - 1), datetime.min.time()
            ),
        )
    ):
        d = created_at
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).date()
        app_counts[d.isoformat()] += 1

    series = []
    totals = {"scanned": 0, "matched": 0, "sent": 0, "ignored": 0, "apps": 0}
    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        data = daily.get(d, {})
        row = {
            "date": d,
            "scanned": data.get("scanned", 0),
            "matched": data.get("matched", 0),
            "sent": data.get("sent", 0),
            "ignored": data.get("ignored", 0),
            "apps": app_counts.get(d, 0),
        }
        for k in totals:
            totals[k] += row[k]
        series.append(row)
    return {"series": series, "totals": totals}


@router.get("/reports")
def reports(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    daily = db.scalars(
        select(ScanReport)
        .where(ScanReport.user_id == user.id, ScanReport.period == "daily")
        .order_by(ScanReport.period_date.desc())
        .limit(14)
    ).all()
    weekly = db.scalars(
        select(ScanReport)
        .where(ScanReport.user_id == user.id, ScanReport.period == "weekly")
        .order_by(ScanReport.period_date.desc())
        .limit(6)
    ).all()
    return {
        "daily": [
            {
                "period_date": r.period_date,
                "data": r.data or {},
                "created_at": r.created_at,
            }
            for r in daily
        ],
        "weekly": [
            {
                "period_date": r.period_date,
                "data": r.data or {},
                "created_at": r.created_at,
            }
            for r in weekly
        ],
    }


@router.get("/skills")
def top_skills(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    skills: Counter = Counter()
    notified = db.scalars(
        select(NotificationLog).where(NotificationLog.user_id == user.id).limit(200)
    ).all()
    if notified:
        for log in notified:
            if log.job:
                for s in log.job.skills_required or []:
                    skills[str(s)] += 1
    else:
        for job in db.scalars(select(Job).limit(300)):
            for s in job.skills_required or []:
                skills[str(s)] += 1
    return {"skills": [{"skill": s, "count": c} for s, c in skills.most_common(limit)]}


@router.get("/funnel")
def funnel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    counts: dict[str, int] = {}
    for status, count in db.execute(
        select(Application.status, func.count())
        .where(Application.user_id == user.id)
        .group_by(Application.status)
    ):
        counts[str(status)] = int(count)
    saved = (
        db.scalar(
            select(func.count())
            .select_from(SavedJob)
            .where(SavedJob.user_id == user.id)
        )
        or 0
    )
    total = sum(counts.values())
    return {
        "total": total,
        "saved": saved,
        "by_status": counts,
        "rates": {
            status: round(count * 100 / total, 1) if total else 0.0
            for status, count in counts.items()
        },
    }
