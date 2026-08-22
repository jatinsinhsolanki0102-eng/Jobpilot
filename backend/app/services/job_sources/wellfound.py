from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import get_settings

from .base import JobSource, RawJob
from .common import (
    PLAYWRIGHT_AVAILABLE,
    dedupe_strs,
    fetch_html,
    make_soup,
    parse_compensation,
    parse_cookie_str,
    parse_iso_datetime,
    parse_work_mode,
    require_playwright,
    sync_playwright,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://wellfound.com"


def _settings_cookies() -> list[dict]:
    return parse_cookie_str(get_settings().WELLFOUND_COOKIES, ".wellfound.com")


def _settings_proxy() -> str | None:
    return get_settings().SCRAPER_PROXY

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Wellfound embeds its search results as Apollo/Next state inside script tags.
_SCRIPT_JS = """
() => {
  const out = [];
  for (const s of document.querySelectorAll('script')) {
    const text = s.textContent || '';
    if (!text.trim()) continue;
    const type = s.getAttribute('type') || '';
    if (type === 'application/json' || s.id === '__NEXT_DATA__') {
      out.push({ id: s.id, text });
    } else if (/__APOLLO_STATE__|window\\.__/i.test(text)) {
      out.push({ id: s.id, text });
    }
  }
  return out;
}
"""


def _collect_scripts(page) -> list[dict]:
    try:
        return page.evaluate(_SCRIPT_JS)
    except Exception:  # noqa: BLE001
        return []


def _parse_blob(text: str) -> Any | None:
    stripped = text.strip()
    if stripped.startswith("window."):
        stripped = stripped[stripped.index("=") + 1 :].strip().rstrip(";").strip()
    try:
        return json.loads(stripped)
    except ValueError:
        return None


def _extract_jobs(root: Any) -> list[tuple[dict, str]]:
    """Find JobListingSearchResult nodes paired with their StartupResult parent."""
    results: list[tuple[dict, str]] = []

    def walk(obj: Any, company: str) -> None:
        if isinstance(obj, dict):
            if obj.get("__typename") == "StartupResult":
                company = obj.get("name") or company
            if obj.get("__typename") == "JobListingSearchResult":
                results.append((obj, company))
            for value in obj.values():
                walk(value, company)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, company)

    walk(root, "")
    if results:
        return results

    # Fallback: standalone job nodes.
    for obj in _walk_all(root):
        if (
            isinstance(obj, dict)
            and obj.get("id")
            and isinstance(obj.get("title"), str)
            and obj.get("title")
            and (obj.get("company_name") or obj.get("startup_name"))
        ):
            results.append((obj, obj.get("company_name") or obj.get("startup_name")))
    return results


def _walk_all(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk_all(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_all(value)


def _to_raw_job(job: dict, company: str) -> RawJob | None:
    title = (job.get("title") or "").strip()
    if not title:
        return None
    job_id = str(job.get("id") or "")
    comp_text = job.get("compensation") or ""
    lo, hi, currency = parse_compensation(comp_text)

    loc_parts: list[str] = []
    for key in ("location", "location_names", "locations", "city", "address"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            loc_parts.append(value.strip())
        elif isinstance(value, list):
            loc_parts.extend(v for v in value if isinstance(v, str) and v.strip())
    location = " · ".join(dedupe_strs(loc_parts)) or None

    remote_flag = job.get("remote")
    work_mode = None
    if remote_flag is True:
        work_mode = "Remote"
    else:
        work_mode = parse_work_mode(location or "")

    url = job.get("url") or f"{BASE_URL}/jobs/{job_id}" if job_id else None
    if isinstance(url, str) and url and not url.startswith("http"):
        url = BASE_URL + url

    return RawJob(
        source_id=f"wellfound:{job_id or re.sub(r'[^a-z0-9]+', '-', title.lower())[:40]}",
        source="wellfound",
        title=title,
        company_name=(company or job.get("company_name") or "Unknown Company").strip(),
        location=location,
        work_mode=work_mode,
        employment_type=None,
        salary_min=lo,
        salary_max=hi,
        salary_currency=currency,
        skills_required=job.get("tags") or job.get("skills") or [],
        description=(job.get("description") or job.get("short_description") or None),
        posted_at=parse_iso_datetime(
            job.get("posted_at") or job.get("postedAt") or job.get("listing_created_at")
        ),
        url=url or None,
    )


def _collect_scripts_html(html: str) -> list[dict]:
    """Same as _collect_scripts but from raw HTML (no browser)."""
    out: list[dict] = []
    try:
        soup = make_soup(html)
    except Exception:  # noqa: BLE001
        return []
    for s in soup.find_all("script"):
        text = s.string or s.get_text() or ""
        if not text.strip():
            continue
        stype = (s.get("type") or "").strip()
        sid = s.get("id") or ""
        if stype == "application/json" or sid == "__NEXT_DATA__":
            out.append({"id": sid, "text": str(text)})
        elif re.search(r"__APOLLO_STATE__|window\.__", str(text), re.IGNORECASE):
            out.append({"id": sid, "text": str(text)})
    return out


class WellfoundSource(JobSource):
    name = "wellfound"

    def _scrape_http(
        self,
        query: str | None,
        location: str | None,
        limit: int,
    ) -> list[RawJob]:
        slug = re.sub(r"[^a-z0-9]+", "-", (query or "").lower()).strip("-")
        if location:
            loc = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
            url = f"{BASE_URL}/role/l/{slug}/{loc}"
        else:
            url = f"{BASE_URL}/role/{slug}" if slug else f"{BASE_URL}/jobs"
        html = fetch_html(url, cookies=get_settings().WELLFOUND_COOKIES)
        if not html:
            logger.warning("Wellfound HTTP fetch blocked or empty for %s", url)
            return []
        jobs: list[RawJob] = []
        for script in _collect_scripts_html(html):
            parsed = _parse_blob(script.get("text") or "")
            if parsed is None:
                continue
            for job, company in _extract_jobs(parsed):
                raw = _to_raw_job(job, company)
                if raw is not None:
                    jobs.append(raw)
                    if len(jobs) >= limit:
                        break
            if len(jobs) >= limit:
                break
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
        slug = re.sub(r"[^a-z0-9]+", "-", (query or "").lower()).strip("-")
        if location:
            loc = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
            url = f"{BASE_URL}/role/l/{slug}/{loc}"
        else:
            url = f"{BASE_URL}/role/{slug}" if slug else f"{BASE_URL}/jobs"
        logger.info("Wellfound search URL: %s", url)

        jobs: list[RawJob] = []
        if not PLAYWRIGHT_AVAILABLE:
            return self._scrape_http(query, location, limit)
        require_playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
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
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                for _ in range(max(1, pages) - 1):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(1200)
                parsed: Any = None
                for script in _collect_scripts(page):
                    parsed = _parse_blob(script.get("text") or "")
                    if parsed is not None:
                        break
                if parsed is None:
                    logger.warning("No embedded JSON found on Wellfound page")
                    return jobs
                for job, company in _extract_jobs(parsed):
                    raw = _to_raw_job(job, company)
                    if raw is not None:
                        jobs.append(raw)
                        if len(jobs) >= limit:
                            break
            finally:
                browser.close()
        return jobs[:limit]
