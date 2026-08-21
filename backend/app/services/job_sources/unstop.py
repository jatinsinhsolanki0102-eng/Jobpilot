from __future__ import annotations

import json
import logging
from urllib.parse import quote

from app.config import get_settings

from .base import JobSource, RawJob
from .common import (
    dedupe_strs,
    parse_compensation,
    parse_cookie_str,
    parse_iso_datetime,
    parse_work_mode,
    require_playwright,
    sync_playwright,
    walk_dicts,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://unstop.com"
API_URL = f"{BASE_URL}/api/public/opportunity/search-result"


def _settings_cookies() -> list[dict]:
    return parse_cookie_str(get_settings().UNSTOP_COOKIES, ".unstop.com")


def _settings_proxy() -> str | None:
    return get_settings().SCRAPER_PROXY

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _find_opportunities(root) -> list[dict]:
    results: list[dict] = []
    for obj in walk_dicts(root):
        if not isinstance(obj, dict) or not obj.get("id"):
            continue
        title = obj.get("opportunity_title") or obj.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        org = obj.get("organisation")
        pub = obj.get("public_url")
        if isinstance(org, dict) and org.get("name"):
            results.append(obj)
        elif isinstance(pub, str) and (
            "internship" in pub.lower() or "/job" in pub.lower()
        ):
            results.append(obj)
    return results


def _skills(obj: dict) -> list[str]:
    raw = obj.get("skills") or obj.get("required_skills") or []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(str(item.get("skill") or item.get("name") or ""))
    return dedupe_strs(out)


def _deadline(obj: dict):
    for key in ("opportunity_deadline", "registration_deadline", "deadline"):
        value = obj.get(key)
        parsed = parse_iso_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _comp_text(obj: dict) -> str:
    for key in ("salary", "stipend", "compensation", "ctc"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _location(obj: dict) -> str | None:
    parts: list[str] = []
    locations = obj.get("locations")
    if isinstance(locations, list):
        for loc in locations:
            if isinstance(loc, str) and loc.strip():
                parts.append(loc.strip())
            elif isinstance(loc, dict):
                for key in ("name", "city", "state"):
                    value = loc.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
                        break
    city = obj.get("city") or obj.get("location")
    if isinstance(city, str) and city.strip():
        parts.append(city.strip())
    addr = obj.get("address_with_country_logo") or {}
    if isinstance(addr, dict):
        for key in ("city", "state", "country_name"):
            value = addr.get(key)
            if isinstance(value, dict):
                value = value.get("name")
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    result = " · ".join(dedupe_strs(parts))
    if result:
        return result
    if str(obj.get("region") or "").lower() == "online":
        return "Remote"
    return None


def _to_raw_job(obj: dict, kind: str) -> RawJob | None:
    title = (obj.get("opportunity_title") or obj.get("title") or "").strip()
    if not title:
        return None
    org = obj.get("organisation") or {}
    company = org.get("name") or obj.get("organization_title") or "Unknown Company"
    pub = obj.get("public_url") or ""
    url = f"{BASE_URL}/{pub.lstrip('/')}" if pub else None

    comp_text = _comp_text(obj)
    lo, hi, currency = parse_compensation(comp_text)
    if lo is None and isinstance(obj.get("min_salary"), (int, float)):
        lo = int(obj.get("min_salary"))
    if hi is None and isinstance(obj.get("max_salary"), (int, float)):
        hi = int(obj.get("max_salary"))
    if lo is not None or hi is not None:
        currency = "INR"
    region = str(obj.get("region") or "").lower()
    format_text = " ".join(
        [
            obj.get("format") or "",
            region,
            obj.get("employment_type") or "",
            obj.get("description") or "",
        ]
    )
    work_mode = None
    if format_text:
        work_mode = parse_work_mode(format_text)
        if work_mode == "Onsite" and region == "online":
            work_mode = "Remote"
    if work_mode is None and region == "online":
        work_mode = "Remote"

    return RawJob(
        source_id=f"unstop:{obj.get('id')}",
        source="unstop",
        title=title,
        company_name=str(company).strip(),
        location=_location(obj),
        work_mode=work_mode,
        employment_type="Internship" if kind == "internships" else "Full-time",
        salary_min=lo,
        salary_max=hi,
        salary_currency=currency,
        experience_required=None,
        description=(obj.get("description") or obj.get("details") or None),
        skills_required=_skills(obj),
        application_deadline=_deadline(obj),
        url=url,
    )


class UnstopSource(JobSource):
    name = "unstop"

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
        pages: int = 1,
    ) -> list[RawJob]:
        """Query Unstop's public opportunity search API via the browser."""
        kinds = ["internships"] if internship else ["jobs"]
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
                try:
                    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45000)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not load Unstop homepage: %s", exc)
                for kind in kinds:
                    for page_no in range(1, max(1, pages) + 1):
                        params = {
                            "opportunity": kind,
                            "page": page_no,
                            "per_page": max(limit, 50),
                        }
                        if query:
                            params["searchTerm"] = query
                        if location:
                            params["location"] = location
                        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
                        url = f"{API_URL}?{qs}"
                        try:
                            payload = page.evaluate(
                                """async (url) => {
                                  const res = await fetch(url, {
                                    headers: { 'Accept': 'application/json, text/plain, */*' }
                                  });
                                  return res.json();
                                }""",
                                url,
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Unstop API request failed: %s", exc)
                            continue
                        for obj in _find_opportunities(payload):
                            raw = _to_raw_job(obj, kind)
                            if raw is not None:
                                jobs.append(raw)
                                if len(jobs) >= limit:
                                    break
                        if len(jobs) >= limit:
                            break
                    if len(jobs) >= limit:
                        break
            finally:
                browser.close()
        return jobs[:limit]
