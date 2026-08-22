from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from .base import JobSource, RawJob
from .common import (
    PLAYWRIGHT_AVAILABLE,
    PWTimeoutError,
    fetch_html,
    make_soup,
    require_playwright,
    sync_playwright,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://internshala.com"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_AMOUNT = r"([\d,]+)"
_SALARY_RE = re.compile(
    rf"â‚¹\s*{_AMOUNT}(?:\s*[-â€“â€”]\s*â‚¹?\s*{_AMOUNT})?\s*/\s*(month|monthly|year|annum|annual)",
    re.IGNORECASE,
)
_LPA_RE = re.compile(
    rf"(?:â‚¹\s*)?({_AMOUNT}(?:\.\d+)?)\s*[-â€“â€”]\s*(?:â‚¹\s*)?({_AMOUNT}(?:\.\d+)?)\s*LPA",
    re.IGNORECASE,
)
_LPA_SINGLE_RE = re.compile(rf"(?:â‚¹\s*)?({_AMOUNT}(?:\.\d+)?)\s*LPA", re.IGNORECASE)

_EXTRACT_JS = """
() => {
  const out = [];
  for (const card of document.querySelectorAll('.individual_internship')) {
    const a = card.querySelector('a.job-title-href');
    if (!a) continue;
    const title = (a.textContent || '').trim();
    if (!title) continue;
    const compEl = card.querySelector('p.company-name');
    const locEls = card.querySelectorAll('.row-1-item.locations span a, .row-1-item.locations span');
    const stipEl = card.querySelector('.stipend');
    const durEl = Array.from(card.querySelectorAll('.detail-row-1 .row-1-item'))
      .find(e => e.querySelector('.ic-16-calendar'));
    const descEl = card.querySelector('.about_job .text');
    const postEl = card.querySelector('.color-labels .status-inactive span');
    out.push({
      id: (card.getAttribute('id') || '').replace(/[^0-9]/g, ''),
      title,
      href: a.getAttribute('href') || '',
      company: compEl ? compEl.textContent.trim() : '',
      locations: Array.from(locEls).map(e => e.textContent.trim()).filter(Boolean),
      stipend: stipEl ? stipEl.textContent.trim() : '',
      duration: durEl ? durEl.textContent.trim() : '',
      description: descEl ? descEl.textContent.trim() : '',
      skills: Array.from(card.querySelectorAll('.job_skill')).map(e => e.textContent.trim()).filter(Boolean),
      posted: postEl ? postEl.textContent.trim() : '',
      empType: card.getAttribute('employment_type') || '',
      cardText: card.innerText,
    });
  }
  return out;
}
"""


def _parse_salary(stipend: str) -> tuple[int | None, int | None]:
    """Parse Internshala stipend strings like 'â‚¹ 13,000 - 18,000 /month'."""
    if not stipend or "unpaid" in stipend.lower():
        return None, None

    def to_int(s: str) -> int:
        return int(s.replace(",", "").replace(".", ""))

    m = _SALARY_RE.search(stipend)
    if m:
        period = m.group(3).lower()
        factor = 1.0 if period in ("month", "monthly") else 1.0 / 12
        lo, hi = to_int(m.group(1)), to_int(m.group(2)) if m.group(2) else None
        return (
            round(lo * factor),
            round(hi * factor) if hi is not None else round(lo * factor),
        )

    m = _LPA_RE.search(stipend)
    if m:
        return round(to_int(m.group(1)) * 100000 / 12), round(
            to_int(m.group(2)) * 100000 / 12
        )

    m = _LPA_SINGLE_RE.search(stipend)
    if m:
        return round(to_int(m.group(1)) * 100000 / 12), round(
            to_int(m.group(1)) * 100000 / 12
        )

    m = re.search(rf"â‚¹\s*{_AMOUNT}", stipend)
    if m:
        v = to_int(m.group(1))
        return v, v

    return None, None


def _parse_posted(text: str) -> datetime | None:
    """Parse 'Just now', 'X days ago', 'X weeks ago', 'X months ago'."""
    if not text:
        return None
    t = text.lower().strip()
    now = datetime.now(timezone.utc)
    if "just now" in t:
        return now
    m = re.search(r"(\d+)\s*(day|hour|week|month)s?\s*ago", t)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit == "day":
        delta = timedelta(days=n)
    elif unit == "hour":
        delta = timedelta(hours=n)
    elif unit == "week":
        delta = timedelta(weeks=n)
    else:
        delta = timedelta(days=30 * n)
    return now - delta


def _parse_deadline(text: str) -> datetime | None:
    """Best-effort parse of 'Apply before X Jul 2026' style deadlines."""
    if not text:
        return None
    m = re.search(
        r"apply\s+before\s+(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", text, re.IGNORECASE
    )
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
    except ValueError:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y"
            )
        except ValueError:
            return None


def _parse_work_mode(text: str) -> str:
    t = text.lower()
    if "work from home" in t or "work-from-home" in t or "remote" in t:
        return "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "Onsite"


def _parse_employment(emp_type: str, card_text: str) -> str:
    if "part time" in card_text.lower():
        return "Part-time"
    return "Internship" if emp_type == "internship" else "Full-time"


def _build_url(query: str | None, internship: bool) -> str:
    kind = "internships" if internship else "jobs"
    if query:
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        return f"{BASE_URL}/{kind}/keywords-{slug}-jobs"
    return f"{BASE_URL}/{kind}/"


def _detail_selectors() -> list[str]:
    return [
        ".about_job .text",
        ".job-detail .text",
        ".internship_details .about_job .text",
        ".details .text",
    ]


def _scrape_list_page(
    page,
    query: str | None,
    location: str | None,
    limit: int,
    internship: bool = True,
    page_no: int = 1,
) -> list[dict]:
    url = _build_url(query, internship)
    if page_no > 1:
        url = f"{url}/page-{page_no}"
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_selector(".individual_internship", timeout=20000)
    except PWTimeoutError:
        logger.warning("No internship cards found on listing page")
        return []
    page.wait_for_timeout(2500)

    items = page.evaluate(_EXTRACT_JS)
    if not items and query:
        # keyword URL may not match; fall back to the unfiltered listing
        page.goto(
            _build_url(None, internship), wait_until="domcontentloaded", timeout=45000
        )
        try:
            page.wait_for_selector(".individual_internship", timeout=20000)
        except PWTimeoutError:
            return []
        page.wait_for_timeout(2500)
        items = page.evaluate(_EXTRACT_JS)

    if location:
        loc_l = location.lower()
        items = [
            i for i in items if any(loc_l in (x or "").lower() for x in i["locations"])
        ]
    return items[:limit]


def _scrape_detail(page, url: str) -> dict:
    """Best-effort detail-page extraction (description, skills, deadline)."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
    except Exception:
        return {}
    info: dict = {}
    for sel in _detail_selectors():
        try:
            el = page.query_selector(sel)
            if el:
                text = (el.inner_text() or "").strip()
                if text:
                    info["description"] = text
                    break
        except Exception:
            continue
    try:
        skills = page.eval_on_selector_all(
            ".job_skill, .skill-tag, .skill_tag",
            "els => Array.from(els).map(e => e.textContent.trim()).filter(Boolean)",
        )
        if skills:
            info["skills"] = skills
    except Exception:
        pass
    try:
        body = page.inner_text("body")
        deadline = _parse_deadline(body)
        if deadline:
            info["deadline"] = deadline
    except Exception:
        pass
    return info


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        v = (i or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def _to_raw_job(item: dict) -> RawJob:
    card_text = " ".join(
        [
            item["title"],
            item.get("company", ""),
            " ".join(item.get("locations", [])),
            item.get("stipend", ""),
            item.get("duration", ""),
            item.get("description", ""),
            item.get("posted", ""),
        ]
    )
    lo, hi = _parse_salary(item.get("stipend", ""))
    locs = " Â· ".join(_dedupe(item.get("locations", [])))
    href = item.get("href", "")
    if href and not href.startswith("http"):
        href = BASE_URL + href
    emp_type = _parse_employment(item.get("empType", ""), card_text)
    return RawJob(
        source_id=f"internshala:{item.get('id') or href.split('/')[-1][:60]}",
        source="internshala",
        title=item["title"],
        company_name=item.get("company") or "Unknown Company",
        location=locs or None,
        work_mode=_parse_work_mode(card_text),
        employment_type=emp_type,
        salary_min=lo,
        salary_max=hi,
        salary_currency="INR",
        experience_required=None if emp_type == "Internship" else "0-3 yrs",
        description=item.get("description") or None,
        skills_required=item.get("skills", []),
        posted_at=_parse_posted(item.get("posted", "") or card_text),
        url=href or None,
    )


class InternshalaSource(JobSource):
    name = "internshala"

    # ---------------- HTTP fallback (no browser needed) ----------------

    def _card_to_item(self, card) -> dict:
        def txt(el):
            return el.get_text(" ", strip=True) if el else ""

        a = card.select_one("a.job-title-href")
        if a is None:
            return {}
        title = txt(a)
        if not title:
            return {}
        locations = [
            txt(s) for s in card.select(".row-1-item.locations span") if txt(s)
        ]
        duration = ""
        for row in card.select(".detail-row-1 .row-1-item"):
            if row.select_one(".ic-16-calendar"):
                duration = txt(row)
                break
        desc_el = card.select_one(".about_job .text, .job-description")
        post_el = card.select_one(".color-labels .status-inactive span")
        return {
            "id": re.sub(r"[^0-9]", "", card.get("id") or ""),
            "title": title,
            "href": a.get("href") or "",
            "company": txt(card.select_one("p.company-name, .company-name")),
            "locations": locations,
            "stipend": txt(card.select_one(".stipend")),
            "duration": duration,
            "description": txt(desc_el),
            "skills": [txt(e) for e in card.select(".job_skill") if txt(e)],
            "posted": txt(post_el),
            "empType": card.get("employment_type") or "",
            "cardText": card.get_text(" ", strip=True),
        }

    def _scrape_http(
        self,
        query: str | None,
        location: str | None,
        limit: int,
        internship: bool,
        pages: int,
        with_details: bool,
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen_ids: set[str] = set()
        for page_no in range(1, max(1, pages) + 1):
            url = _build_url(query, internship)
            if page_no > 1:
                url = f"{url}/page-{page_no}"
            html = fetch_html(url)
            items: list[dict] = []
            if html:
                soup = make_soup(html)
                items = [
                    i for i in (self._card_to_item(c) for c in soup.select(".individual_internship")) if i
                ]
            if not items and query and page_no == 1:
                html = fetch_html(_build_url(None, internship))
                if html:
                    soup = make_soup(html)
                    items = [
                        i for i in (self._card_to_item(c) for c in soup.select(".individual_internship")) if i
                    ]
            if location:
                loc_l = location.lower()
                items = [
                    i
                    for i in items
                    if any(loc_l in (x or "").lower() for x in i["locations"])
                ]
            fresh = [i for i in items if i.get("id") and i["id"] not in seen_ids]
            for i in fresh:
                seen_ids.add(i["id"])
            jobs.extend(_to_raw_job(i) for i in fresh)
            if len(fresh) < limit or page_no >= max(1, pages):
                break

        if with_details:
            for job in jobs[: min(limit, 8)]:
                if not job.url:
                    continue
                detail = self._detail_http(job.url)
                if detail.get("description"):
                    job.description = detail["description"]
                if detail.get("skills"):
                    job.skills_required = detail["skills"]
                if detail.get("deadline"):
                    job.application_deadline = detail["deadline"]
        return jobs[:limit]

    def _detail_http(self, url: str) -> dict:
        html = fetch_html(url)
        if not html:
            return {}
        soup = make_soup(html)
        info: dict = {}
        for sel in _detail_selectors():
            el = soup.select_one(sel)
            if el:
                text = el.get_text(" ", strip=True)
                if text:
                    info["description"] = text
                    break
        skills = [
            e.get_text(strip=True)
            for e in soup.select(".job_skill, .skill-tag, .skill_tag")
            if e.get_text(strip=True)
        ]
        if skills:
            info["skills"] = skills
        deadline = _parse_deadline(soup.get_text(" ", strip=True)[:20000])
        if deadline:
            info["deadline"] = deadline
        return info

    def scrape(
        self,
        query: str | None = None,
        location: str | None = None,
        internship: bool = True,
        limit: int = 20,
        with_details: bool = True,
        pages: int = 1,
        min_stipend: int | None = None,
        work_mode: str | None = None,
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        if not PLAYWRIGHT_AVAILABLE:
            jobs = self._scrape_http(query, location, limit, internship, pages, with_details)
        else:
            require_playwright()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=_USER_AGENT, viewport={"width": 1366, "height": 900}
                )
                page = ctx.new_page()
                try:
                    seen_ids: set[str] = set()
                    for page_no in range(1, max(1, pages) + 1):
                        items = _scrape_list_page(
                            page, query, location, limit, internship, page_no
                        )
                        fresh = [i for i in items if i.get("id") not in seen_ids]
                        for i in fresh:
                            if i.get("id"):
                                seen_ids.add(i["id"])
                        jobs.extend(_to_raw_job(i) for i in fresh)
                        if len(fresh) < limit or page_no >= max(1, pages):
                            break

                    if min_stipend:
                        jobs = [j for j in jobs if (j.salary_min or 0) >= min_stipend]
                    if work_mode:
                        wm = work_mode.lower()
                        jobs = [j for j in jobs if (j.work_mode or "").lower() == wm]
                    jobs = jobs[:limit]

                    if with_details:
                        detail_limit = min(limit, 12)
                        for job in jobs[:detail_limit]:
                            if not job.url:
                                continue
                            detail = _scrape_detail(page, job.url)
                            if detail.get("description"):
                                job.description = detail["description"]
                            if detail.get("skills"):
                                job.skills_required = detail["skills"]
                            if detail.get("deadline"):
                                job.application_deadline = detail["deadline"]
                finally:
                    browser.close()
        return jobs
