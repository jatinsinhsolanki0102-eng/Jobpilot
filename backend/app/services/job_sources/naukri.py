from __future__ import annotations

import hashlib
import logging
import re

from app.config import get_settings

from .base import JobSource, RawJob
from .common import (
    PWTimeoutError,
    dedupe_strs,
    parse_cookie_str,
    parse_experience,
    parse_inr_salary,
    parse_relative_posted,
    parse_work_mode,
    require_playwright,
    sync_playwright,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.naukri.com"


def _settings_cookies() -> list[dict]:
    return parse_cookie_str(get_settings().NAUKRI_COOKIES, ".naukri.com")


def _settings_proxy() -> str | None:
    return get_settings().SCRAPER_PROXY

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_EXTRACT_JS = """
() => {
  const out = [];
  const cards = document.querySelectorAll('.jobTuple, article.jobTuple, [class*="job-listing-card"]');
  for (const card of cards) {
    const a = card.querySelector('a.title') || card.querySelector('a[href*="/job-listings"]');
    if (!a) continue;
    const title = (a.textContent || '').trim().replace(/\\s+/g, ' ');
    if (!title) continue;
    const compEl = card.querySelector('a.subTitle') || card.querySelector('.subTitle');
    const locEls = card.querySelectorAll(
      '.row1 .fleft, ul.fleft li, [class*="job-location"] span, .location, .jobTupleHeader .fleft'
    );
    const salEl = card.querySelector('.salary, [class*="salary"]');
    const expEl = card.querySelector('.exp, [class*="experience"]');
    const postEl = card.querySelector('span.postedd, .job-posted, [class*="posted"]');
    const descEl = card.querySelector('.job-description, .desc, [class*="job-description"]');
    const skillEls = card.querySelectorAll('.tag, [class*="skill"]');
    out.push({
      title,
      href: a.getAttribute('href') || '',
      company: compEl ? compEl.textContent.trim() : '',
      locations: Array.from(locEls).map(e => e.textContent.trim()).filter(Boolean),
      salary: salEl ? salEl.textContent.trim() : '',
      experience: expEl ? expEl.textContent.trim() : '',
      posted: postEl ? postEl.textContent.trim() : '',
      description: descEl ? descEl.textContent.trim() : '',
      skills: Array.from(skillEls).map(e => e.textContent.trim()).filter(Boolean),
      text: card.innerText,
    });
  }
  return out;
}
"""


def _build_url(query: str | None, location: str | None, page_no: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (query or "jobs").lower()).strip("-")
    url = f"{BASE_URL}/{slug}-jobs"
    if location:
        loc = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
        url = f"{url}-in-{loc}"
    if page_no > 1:
        url = f"{url}-{page_no}"
    return url


def _job_id(item: dict) -> str:
    m = re.search(r"(\d{6,})$", (item.get("href") or "").rstrip("/"))
    if m:
        return m.group(1)
    digest = hashlib.sha1((item.get("href") or item.get("title") or "").encode()).hexdigest()[:16]
    return digest


def _scrape_list(page, url: str) -> list[dict]:
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_selector(".jobTuple, [class*='job-listing-card']", timeout=20000)
    except PWTimeoutError:
        try:
            body = page.inner_text("body")
        except Exception:  # noqa: BLE001
            body = ""
        if "not found" in body.lower() or "robot" in body.lower() or "captcha" in body.lower():
            logger.warning("Naukri blocked or empty results (anti-bot) for %s", url)
        else:
            logger.warning("No Naukri job cards found on %s", url)
        return []
    page.wait_for_timeout(1500)
    return page.evaluate(_EXTRACT_JS)


def _to_raw_job(item: dict) -> RawJob | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    href = item.get("href") or ""
    if href and not href.startswith("http"):
        href = BASE_URL + href
    card_text = " ".join(
        [
            title,
            item.get("company", ""),
            " ".join(item.get("locations", [])),
            item.get("salary", ""),
            item.get("experience", ""),
            item.get("description", ""),
            item.get("posted", ""),
        ]
    )
    lo, hi = parse_inr_salary(item.get("salary", "") or card_text)
    locs = " · ".join(dedupe_strs(item.get("locations", []))) or None
    experience = parse_experience(item.get("experience", "")) or None
    return RawJob(
        source_id=f"naukri:{_job_id(item)}",
        source="naukri",
        title=title,
        company_name=(item.get("company") or "Unknown Company").strip(),
        location=locs,
        work_mode=parse_work_mode(card_text),
        employment_type="Full-time",
        salary_min=lo,
        salary_max=hi,
        salary_currency="INR",
        experience_required=experience,
        description=(item.get("description") or None),
        skills_required=dedupe_strs(item.get("skills", [])),
        posted_at=parse_relative_posted(item.get("posted", "") or card_text),
        url=href or None,
    )


class NaukriSource(JobSource):
    name = "naukri"

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
        pages: int = 1,
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        require_playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx_opts: dict = {"user_agent": _USER_AGENT, "viewport": {"width": 1366, "height": 900}}
            proxy = _settings_proxy()
            if proxy:
                ctx_opts["proxy"] = {"server": proxy}
            ctx = browser.new_context(**ctx_opts)
            cookies = _settings_cookies()
            if cookies:
                ctx.add_cookies(cookies)
            page = ctx.new_page()
            try:
                seen_ids: set[str] = set()
                for page_no in range(1, max(1, pages) + 1):
                    items = _scrape_list(page, _build_url(query, location, page_no))
                    fresh = []
                    for item in items:
                        jid = _job_id(item)
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)
                        raw = _to_raw_job(item)
                        if raw is not None:
                            fresh.append(raw)
                    jobs.extend(fresh)
                    if len(fresh) < 20 or page_no >= max(1, pages):
                        break
            finally:
                browser.close()
        return jobs[:limit]
