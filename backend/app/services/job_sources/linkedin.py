from __future__ import annotations

import logging
import re
from urllib.parse import urlencode

from app.config import get_settings

from .base import JobSource, RawJob
from .common import (
    PLAYWRIGHT_AVAILABLE,
    PWTimeoutError,
    fetch_html,
    make_soup,
    parse_cookie_str,
    parse_iso_datetime,
    parse_work_mode,
    require_playwright,
    sync_playwright,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.linkedin.com"
SEARCH_URL = f"{BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search"


def _settings_cookies() -> list[dict]:
    return parse_cookie_str(get_settings().LINKEDIN_COOKIES, ".linkedin.com")


def _settings_proxy() -> str | None:
    return get_settings().SCRAPER_PROXY

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_EXTRACT_JS = """
() => {
  const out = [];
  for (const card of document.querySelectorAll('div.base-search-card')) {
    const a = card.querySelector('a.base-card__full-link')
      || card.querySelector('a.base-search-card--link');
    if (!a) continue;
    const h3 = card.querySelector('h3.base-search-card__title');
    const title = ((h3 ? h3.textContent : a.textContent) || '').trim().replace(/\\s+/g, ' ');
    if (!title) continue;
    const compEl = card.querySelector('h4.base-search-card__subtitle');
    const locEl = card.querySelector('span.job-search-card__location')
      || card.querySelector('.base-search-card__metadata span');
    const timeEl = card.querySelector('time.job-search-card__listdate');
    const urn = a.getAttribute('data-entity-urn') || card.getAttribute('data-entity-urn') || '';
    out.push({
      title,
      href: a.getAttribute('href') || '',
      company: compEl ? (compEl.querySelector('a') || compEl).textContent.trim() : '',
      location: locEl ? locEl.textContent.trim() : '',
      postedAt: timeEl ? (timeEl.getAttribute('datetime') || '') : '',
      urn,
    });
  }
  return out;
}
"""


def _build_url(query: str | None, location: str | None, start: int, internship: bool = True) -> str:
    params: dict[str, str] = {"start": str(start), "f_TPR": "r604800"}
    if internship:
        params["f_JT"] = "I"
    if query:
        params["keywords"] = query
    if location:
        params["location"] = location
    return f"{SEARCH_URL}?{urlencode(params)}"


def _job_id(item: dict) -> str:
    m = re.search(r"(\d+)", item.get("urn") or item.get("href") or "")
    return m.group(1) if m else item.get("href") or item.get("title") or ""


def _scrape_list(page, url: str) -> list[dict]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("div.base-search-card", timeout=20000)
        page.wait_for_timeout(1500)
    except PWTimeoutError:
        logger.warning("LinkedIn returned no job cards (rate-limited or blocked)")
        return []
    return page.evaluate(_EXTRACT_JS)


def _to_raw_job(item: dict) -> RawJob | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    href = item.get("href") or ""
    if href and not href.startswith("http"):
        href = BASE_URL + href
    location = (item.get("location") or "").strip() or None
    return RawJob(
        source_id=f"linkedin:{_job_id(item)}",
        source="linkedin",
        title=title,
        company_name=(item.get("company") or "Unknown Company").strip(),
        location=location,
        work_mode=parse_work_mode(location or "") if location else None,
        employment_type=None,
        salary_currency="INR",
        posted_at=parse_iso_datetime(item.get("postedAt")),
        url=href or None,
    )


class LinkedInSource(JobSource):
    name = "linkedin"

    def _card_to_item(self, card) -> dict:
        def txt(el):
            return el.get_text(" ", strip=True) if el else ""

        a = card.select_one("a.base-card__full-link") or card.select_one(
            "a.base-search-card--link"
        )
        if a is None:
            return {}
        h3 = card.select_one("h3.base-search-card__title")
        title = txt(h3) or txt(a)
        if not title:
            return {}
        comp_el = card.select_one("h4.base-search-card__subtitle")
        loc_el = card.select_one("span.job-search-card__location") or card.select_one(
            ".base-search-card__metadata span"
        )
        time_el = card.select_one("time.job-search-card__listdate")
        return {
            "title": re.sub(r"\s+", " ", title),
            "href": a.get("href") or "",
            "company": (
                txt(comp_el.select_one("a")) or txt(comp_el)
                if comp_el
                else ""
            ),
            "location": txt(loc_el),
            "postedAt": (time_el.get("datetime") or "") if time_el else "",
            "urn": a.get("data-entity-urn") or card.get("data-entity-urn") or "",
        }

    def _scrape_http(
        self,
        query: str | None,
        location: str | None,
        internship: bool,
        limit: int,
        pages: int,
    ) -> list[RawJob]:
        """Fetch LinkedIn's guest job search HTML without a browser."""
        jobs: list[RawJob] = []
        seen_ids: set[str] = set()
        start = 0
        max_starts = max(1, pages) * 25
        cookies = get_settings().LINKEDIN_COOKIES
        while len(jobs) < limit and start < max_starts:
            html = fetch_html(
                _build_url(query, location, start, internship), cookies=cookies
            )
            items: list[dict] = []
            if html:
                soup = make_soup(html)
                items = [i for i in (self._card_to_item(c) for c in soup.select("div.base-search-card")) if i]
            fresh_raws: list[RawJob] = []
            for item in items:
                jid = _job_id(item)
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)
                raw = _to_raw_job(item)
                if raw is not None:
                    fresh_raws.append(raw)
            jobs.extend(fresh_raws)
            if len(items) < 25:
                break
            start += 25
        return jobs[:limit]

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
        pages: int = 1,
    ) -> list[RawJob]:
        """Scrape the LinkedIn guest (logged-out) job search endpoint.

        LinkedIn aggressively rate-limits automated access, so this uses the
        public guest HTML endpoint and a single listing page per call.
        Detail pages are intentionally not fetched to avoid IP blocks.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return self._scrape_http(query, location, internship, limit, pages)
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
                start = 0
                max_starts = max(1, pages) * 25
                while len(jobs) < limit and start < max_starts:
                    items = _scrape_list(page, _build_url(query, location, start, internship))
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
                    if len(items) < 25:
                        break
                    start += 25
            finally:
                browser.close()
        return jobs[:limit]
