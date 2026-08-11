from __future__ import annotations

import html
import logging
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import func, select

from ..config import get_settings
from ..database import SessionLocal
from ..models import (
    Application,
    Job,
    Notification,
    NotificationLog,
    Preference,
    Resume,
    SavedJob,
    TelegramLink,
    TelegramLinkCode,
    User,
)

logger = logging.getLogger(__name__)
settings = get_settings()

_API = "https://api.telegram.org"


def escape_html(text: str | None) -> str:
    return html.escape(text or "", quote=False)


def _fmt_salary(job: dict) -> str:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if not lo and not hi:
        return "Not disclosed"
    fmt = lambda n: f"₹{n:,.0f}"
    if lo and hi and hi != lo:
        return f"{fmt(lo)} - {fmt(hi)}/month"
    return f"{fmt(lo or hi or 0)}/month"


def _deadline_str(job: dict) -> str:
    d = job.get("application_deadline")
    if not d:
        return "-"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace("Z", "+00:00")).date()
        except ValueError:
            return d
    return d.strftime("%d %b %Y")


def _posted_str(job: dict) -> str:
    posted = job.get("posted_at") or job.get("created_at")
    if not posted:
        return "Recently"
    if isinstance(posted, str):
        try:
            posted = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        except ValueError:
            return "Recently"
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - posted).days
    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


def format_job_alert(job: dict, match: dict | None) -> str:
    skills = match or {}
    matched = ", ".join(skills.get("matched_skills", [])[:8]) or "-"
    missing = ", ".join(skills.get("missing_skills", [])[:8]) or "-"
    score = skills.get("score")
    fit = job.get("preference_fit")
    reason = (
        "Matches your resume skills and fits your stated preferences."
        if fit is None
        else f"Strong match for your resume and {fit:.0f}% fit with your preferences."
    )

    lines = [
        "🚀 <b>New Opportunity Found</b>",
        "",
        "🏢 <b>Company</b>",
        escape_html(job.get("company_name") or "-"),
        "",
        "💼 <b>Role</b>",
        escape_html(job.get("title") or "-"),
        "",
        "📍 <b>Location</b>",
        escape_html(job.get("location") or "Remote")
        + (f" ({escape_html(job.get('work_mode'))})" if job.get("work_mode") else ""),
        "",
        "💵 <b>Stipend</b>",
        _fmt_salary(job),
        "",
        "🌐 <b>Source</b>",
        escape_html(job.get("source") or "JobPilot"),
        "",
        "⏱ <b>Duration</b>",
        escape_html(job.get("experience_required") or "Not specified"),
        "",
    ]
    if score is not None:
        lines += ["🎯 <b>AI Match Score</b>", f"{score:.0f}%", ""]
    lines += [
        "🧩 <b>Matching Skills</b>",
        escape_html(matched),
        "",
        "❌ <b>Missing Skills</b>",
        escape_html(missing),
        "",
        "🕐 <b>Posted</b>",
        _posted_str(job),
        "",
        "📅 <b>Deadline</b>",
        _deadline_str(job),
        "",
        "🔗 <b>Apply</b>",
        job.get("url") or "-",
        "",
        "💡 <b>Why this job</b>",
        escape_html(reason),
    ]
    return "\n".join(lines)


def format_daily_summary(data: dict) -> str:
    best = data.get("best") or {}
    lines = [
        "📊 <b>Daily Opportunity Report</b>",
        "",
        f"🔎 Jobs Scanned: <b>{data.get('scanned', 0)}</b>",
        f"✅ Matched: <b>{data.get('matched', 0)}</b>",
        f"📨 Notifications Sent: <b>{data.get('sent', 0)}</b>",
        f"🚫 Ignored: <b>{data.get('ignored', 0)}</b>",
        f"🎯 Average Match Score: <b>{data.get('avg_score', 0):.0f}%</b>",
    ]
    if best.get("title"):
        lines += [
            "",
            "🏆 <b>Best Opportunity</b>",
            f"{escape_html(best['title'])} @ {escape_html(best.get('company', ''))} "
            f"({best.get('score', 0):.0f}%)",
        ]
    return "\n".join(lines)


def format_weekly_report(data: dict) -> str:
    lines = [
        "🗓 <b>Weekly Report</b>",
        "",
        f"🔎 Total Jobs Scanned: <b>{data.get('scanned', 0)}</b>",
        f"✅ Relevant Jobs: <b>{data.get('matched', 0)}</b>",
        f"📨 Notifications Sent: <b>{data.get('sent', 0)}</b>",
        f"📁 Applications Submitted: <b>{data.get('applications', 0)}</b>",
        f"📞 Interview Calls: <b>{data.get('interviews', 0)}</b>",
        f"🎯 Average Match Score: <b>{data.get('avg_score', 0):.0f}%</b>",
    ]
    skills = data.get("top_skills") or []
    if skills:
        lines += ["", "🔥 <b>Most Requested Skills</b>"]
        lines += [escape_html(s) for s in skills[:8]]
    return "\n".join(lines)


class TelegramBot:
    def __init__(self) -> None:
        self.token: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._client = httpx.Client(timeout=45)
        self._configure()

    def _configure(self) -> None:
        self.token = settings.TELEGRAM_BOT_TOKEN or None

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _url(self, method: str) -> str:
        return f"{_API}/bot{self.token}/{method}"

    def send_message(
        self, chat_id: str | int, text: str, parse_mode: str = "HTML"
    ) -> bool:
        if not self.available:
            return False
        try:
            r = self._client.post(
                self._url("sendMessage"),
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            ok = r.status_code == 200 and r.json().get("ok")
            if not ok:
                logger.warning("Telegram send failed: %s", r.text[:300])
            return bool(ok)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram send error: %s", exc)
            return False

    # ---------------- command handling ----------------

    def _get_user_for_chat(self, chat_id: str) -> User | None:
        db = SessionLocal()
        try:
            link = db.scalar(
                select(TelegramLink).where(TelegramLink.chat_id == str(chat_id))
            )
            if link is None:
                return None
            return db.get(User, link.user_id)
        finally:
            db.close()

    def handle_message(
        self, chat_id: str | int, text: str, username: str | None
    ) -> None:
        chat = str(chat_id)
        if not text:
            return
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        handlers = {
            "/start": self._cmd_start,
            "/link": self._cmd_link,
            "/profile": self._cmd_profile,
            "/jobs": self._cmd_jobs,
            "/top": self._cmd_top,
            "/search": self._cmd_search,
            "/saved": self._cmd_saved,
            "/status": self._cmd_status,
            "/help": self._cmd_help,
        }
        handler = handlers.get(cmd)
        if handler is None:
            self.send_message(
                chat, "Unknown command. Type /help to see available commands."
            )
            return
        handler(chat, arg, username)

    def _cmd_start(self, chat: str, arg: str, username: str | None) -> None:
        self.send_message(
            chat,
            "👋 <b>Welcome to JobPilot AI!</b>\n\n"
            "I watch Internshala, LinkedIn, Unstop, Adzuna and Remotive for "
            "opportunities matching your resume and send you the best ones "
            "automatically.\n\n"
            "To connect this chat to your JobPilot account:\n"
            "1. Open the JobPilot web app → <b>Telegram</b> page\n"
            "2. Click <b>Link Telegram</b> to get a 6-digit code\n"
            "3. Send me: <code>/link YOURCODE</code>\n\n"
            "Type /help to see all commands.",
        )

    def _cmd_link(self, chat: str, arg: str, username: str | None) -> None:
        code = arg.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{6}", code):
            self.send_message(
                chat, "Send me a 6-digit code like <code>/link 12AB34</code>."
            )
            return
        db = SessionLocal()
        try:
            record = db.scalar(
                select(TelegramLinkCode).where(TelegramLinkCode.code == code)
            )
            if record is None or record.used:
                self.send_message(chat, "❌ Invalid or already-used code.")
                return
            if record.created_at.replace(tzinfo=timezone.utc) < datetime.now(
                timezone.utc
            ) - timedelta(minutes=15):
                self.send_message(
                    chat,
                    "❌ This code has expired. Generate a new one from the web app.",
                )
                return
            record.used = True
            link = db.scalar(
                select(TelegramLink).where(TelegramLink.user_id == record.user_id)
            )
            if link is None:
                link = TelegramLink(user_id=record.user_id, chat_id=chat)
                db.add(link)
            link.chat_id = chat
            link.username = username
            link.enabled = True
            db.commit()
            self.send_message(
                chat,
                "✅ <b>Account linked!</b>\n\n"
                "Your Telegram chat is now connected to your JobPilot account. "
                "I'll start sending you matched opportunities automatically.",
            )
        finally:
            db.close()

    def _cmd_profile(self, chat: str, arg: str, username: str | None) -> None:
        user = self._get_user_for_chat(chat)
        if user is None:
            self._not_linked(chat)
            return
        db = SessionLocal()
        try:
            resume = db.scalar(
                select(Resume)
                .where(Resume.user_id == user.id)
                .order_by(Resume.created_at.desc())
                .limit(1)
            )
            pref = db.query(Preference).filter(Preference.user_id == user.id).first()
            skills = (
                ", ".join(s["name"] for s in (resume.skills or [])[:12])
                if resume
                else ""
            )
            lines = [
                "👤 <b>Your Profile</b>",
                "",
                f"Name: {escape_html(user.full_name or '-')}",
                f"Email: {escape_html(user.email)}",
            ]
            if resume:
                lines += [
                    "",
                    f"📄 Resume: <code>{escape_html(resume.filename)}</code>",
                    f"🧠 Top Skills: {escape_html(skills or '-')}",
                ]
            else:
                lines += [
                    "",
                    "📄 Resume: <b>Not uploaded</b> — upload one on the web app.",
                ]
            if pref:
                lines += [
                    "",
                    "⚙️ <b>Preferences</b>",
                    f"Type: {escape_html(pref.job_type or 'Any')}",
                    f"Work: {escape_html(', '.join(pref.work_modes or []) or 'Any')}",
                    f"Locations: {escape_html(', '.join(pref.locations or []) or 'Any')}",
                    f"Min salary: {('₹' + str(pref.salary_min)) if pref.salary_min else 'Any'}",
                    f"Domains: {escape_html(', '.join(pref.domains or []) or 'Any')}",
                ]
            self.send_message(chat, "\n".join(lines))
        finally:
            db.close()

    def _cmd_jobs(self, chat: str, arg: str, username: str | None) -> None:
        user = self._get_user_for_chat(chat)
        if user is None:
            self._not_linked(chat)
            return
        db = SessionLocal()
        try:
            resume = db.scalar(
                select(Resume)
                .where(Resume.user_id == user.id)
                .order_by(Resume.created_at.desc())
                .limit(1)
            )
            if resume is None or not resume.raw_text:
                self.send_message(
                    chat, "Upload a resume first on the JobPilot web app."
                )
                return
            pref = db.query(Preference).filter(Preference.user_id == user.id).first()
            jobs = list(
                db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))
            )
            from ..services.matching import rank_jobs
            from ..services.serializers import job_to_dict, pref_to_dict

            ranked = rank_jobs(
                resume.raw_text,
                resume.skills,
                pref_to_dict(pref),
                [job_to_dict(j) for j in jobs],
            )
            top = ranked[:5]
            if not top:
                self.send_message(
                    chat, "No jobs found yet. Run a sync from the web app first."
                )
                return
            lines = ["🏆 <b>Today's Best Matches</b>", ""]
            for i, j in enumerate(top, 1):
                lines.append(
                    f"{i}. <b>{escape_html(j['title'])}</b> @ {escape_html(j['company_name'])}"
                    f"\n   {j['match']['score']:.0f}% match · {escape_html(j.get('location') or 'Remote')}"
                    f"\n   [{escape_html(j.get('source') or 'JobPilot')}] {j.get('url') or '-'}"
                )
            self.send_message(chat, "\n".join(lines))
        finally:
            db.close()

    def _cmd_top(self, chat: str, arg: str, username: str | None) -> None:
        self._cmd_jobs(chat, arg, username)

    def _cmd_search(self, chat: str, arg: str, username: str | None) -> None:
        query = arg.strip()
        if not query:
            self.send_message(
                chat,
                "Usage: <code>/search python</code> — I'll find matching jobs "
                "across Internshala, LinkedIn, Unstop, Adzuna and Remotive.",
            )
            return
        self.send_message(
            chat, f"🔎 Searching all platforms for <b>{escape_html(query)}</b>…"
        )
        from ..services.job_sources import SOURCE_CLASSES

        found: list = []
        for name, cls in SOURCE_CLASSES.items():
            try:
                batch = cls().scrape(
                    query=query, internship=True, limit=3, with_details=False
                )
                found.extend(batch)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Telegram search failed for %s: %s", name, exc)
        if not found:
            self.send_message(
                chat,
                f"No opportunities found for <b>{escape_html(query)}</b> "
                "right now.",
            )
            return
        lines = [f"🔍 <b>Results for: {escape_html(query)}</b>", ""]
        for j in found[:10]:
            lines.append(
                f"• <b>{escape_html(j.title)}</b> @ {escape_html(j.company_name)}"
                f"\n  {escape_html(j.location or 'Remote')} · {_fmt_salary(j.model_dump())}"
                f"\n  [{escape_html(j.source)}] {j.url or '-'}"
            )
        self.send_message(chat, "\n".join(lines))

    def _cmd_saved(self, chat: str, arg: str, username: str | None) -> None:
        user = self._get_user_for_chat(chat)
        if user is None:
            self._not_linked(chat)
            return
        db = SessionLocal()
        try:
            saved = list(
                db.scalars(
                    select(SavedJob)
                    .where(SavedJob.user_id == user.id)
                    .order_by(SavedJob.created_at.desc())
                    .limit(10)
                )
            )
            if not saved:
                self.send_message(
                    chat, "You have no saved jobs. Save jobs from the web app first."
                )
                return
            lines = ["🔖 <b>Saved Jobs</b>", ""]
            for s in saved:
                if s.job is None:
                    continue
                lines.append(
                    f"• <b>{escape_html(s.job.title)}</b> @ {escape_html(s.job.company_name)}"
                    f"\n  {s.job.url or '-'}"
                )
            self.send_message(chat, "\n".join(lines))
        finally:
            db.close()

    def _cmd_status(self, chat: str, arg: str, username: str | None) -> None:
        user = self._get_user_for_chat(chat)
        if user is None:
            self._not_linked(chat)
            return
        db = SessionLocal()
        try:
            ns = user.notification_settings
            link = user.telegram_link
            total_jobs = db.scalar(select(func.count()).select_from(Job)) or 0
            sent = (
                db.scalar(
                    select(func.count())
                    .select_from(NotificationLog)
                    .where(
                        NotificationLog.user_id == user.id,
                        NotificationLog.channel == "telegram",
                    )
                )
                or 0
            )
            lines = [
                "🖥 <b>System Status</b>",
                "",
                f"Bot: {'✅ Online' if self.available else '⚠️ Token not set'}",
                f"Account: {'✅ Linked' if link and link.enabled else '❌ Not linked'}",
                f"Notifications: {'✅ Enabled' if (ns and ns.notify_enabled) else '⏸ Disabled'}",
                f"Min match score: {ns.min_match_score if ns else 30}%",
                f"Scan interval: every {ns.scheduler_interval_minutes if ns else 60} min",
                f"Notifications sent: {sent}",
                f"Jobs in store: {total_jobs}",
                f"Scheduler: {'✅ Running' if settings.SCHEDULER_ENABLED else '⛔ Off'}",
            ]
            self.send_message(chat, "\n".join(lines))
        finally:
            db.close()

    def _cmd_help(self, chat: str, arg: str, username: str | None) -> None:
        self.send_message(
            chat,
            "🤖 <b>JobPilot AI Commands</b>\n\n"
            "/start — Welcome message\n"
            "/link CODE — Link this chat to your account\n"
            "/profile — Resume summary + preferences\n"
            "/jobs — Today's best matches\n"
            "/top — Highest AI-matched opportunities\n"
            "/search python — Search all platforms\n"
            "/saved — Your saved jobs\n"
            "/status — System status\n"
            "/help — This help",
        )

    def _not_linked(self, chat: str) -> None:
        self.send_message(
            chat,
            "🔒 Your Telegram isn't linked yet.\n"
            "Open the JobPilot web app → Telegram page → Link Telegram, "
            "then send me <code>/link YOURCODE</code>.",
        )

    # ---------------- polling ----------------

    def _get_updates(self, offset: int) -> list[dict]:
        r = self._client.post(
            self._url("getUpdates"),
            json={"offset": offset, "timeout": 25, "allowed_updates": ["message"]},
            timeout=40,
        )
        data = r.json()
        if not data.get("ok"):
            logger.warning("getUpdates error: %s", r.text[:300])
            return []
        return data.get("result", [])

    def _run_polling(self) -> None:
        offset = 0
        logger.info("Telegram bot polling started")
        while not self._stop.is_set():
            try:
                updates = self._get_updates(offset)
                for upd in updates:
                    offset = upd.get("update_id", offset) + 1
                    msg = upd.get("message") or {}
                    chat = (msg.get("chat") or {}).get("id")
                    text = msg.get("text") or ""
                    username = (msg.get("from") or {}).get("username")
                    if chat is not None:
                        self.handle_message(chat, text, username)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Telegram polling error: %s", exc)
                self._stop.wait(10)

    def start(self) -> None:
        if not self.available:
            logger.warning(
                "TELEGRAM_BOT_TOKEN not set; Telegram notifications disabled"
            )
            return
        self._configure()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_polling, daemon=True, name="telegram-poll"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


bot = TelegramBot()
