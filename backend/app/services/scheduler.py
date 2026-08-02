from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import get_settings
from .pipeline import sync_pass_all
from .reports import send_daily_summaries, send_weekly_reports
from .telegram import bot

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return None

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        sync_pass_all,
        IntervalTrigger(minutes=15),
        id="sync_pass",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        send_daily_summaries,
        CronTrigger(hour=settings.DAILY_SUMMARY_HOUR, minute=0),
        id="daily_summary",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        send_weekly_reports,
        CronTrigger(
            day_of_week=settings.WEEKLY_REPORT_DAY,
            hour=settings.WEEKLY_REPORT_HOUR,
            minute=0,
        ),
        id="weekly_report",
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info("Background scheduler started")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def start_background_services() -> None:
    bot.start()
    start_scheduler()


def stop_background_services() -> None:
    stop_scheduler()
    bot.stop()
