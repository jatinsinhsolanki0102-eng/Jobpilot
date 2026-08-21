from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

try:
    from playwright.sync_api import TimeoutError as PWTimeoutError
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    # Playwright is optional (slim deploys like Belmo skip it).
    # Browser-based scrapers must call require_playwright() before use.
    PWTimeoutError = Exception  # type: ignore[assignment,misc]
    sync_playwright = None  # type: ignore[assignment]
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)


def require_playwright() -> None:
    """Raise a clear error if a browser-based scraper is used without playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "This job source requires 'playwright', which is not installed "
            "on this deployment (browser-based scraping is disabled)."
        )


def parse_cookie_str(raw: str | None, domain: str) -> list[dict]:
    """Parse a 'name=value; name2=value2' cookie string into Playwright cookies."""
    if not raw:
        return []
    out: list[dict] = []
    for part in raw.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        if name.strip():
            out.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": domain,
                    "path": "/",
                }
            )
    return out


_NUM = r"([\d][\d,]*(?:\.\d+)?)"

_UNITS = (
    r"(?:"
    r"per\s*month|per\s*annum|per\s*year|"  # longest phrases first
    r"lakhs?|lacs?|lpa|l|"
    r"annum|annual|yearly|monthly|month|year|"
    r"/mo|/yr|/month|/year|/hr|/hour|"
    r"hour|hr|pa|mo|yr"
    r")"
)

_RANGE_RE = re.compile(
    rf"(?:₹|rs\.?|inr)?\s*{_NUM}\s*({_UNITS})?\s*"
    rf"(?:[-–—~]+\s*|\bto\b\s*)"
    rf"(?:₹|rs\.?|inr)?\s*{_NUM}\s*({_UNITS})?",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(
    rf"(?:₹|rs\.?|inr)?\s*{_NUM}\s*({_UNITS})?",
    re.IGNORECASE,
)

_UNIT_FACTOR = {
    "mo": 1.0,
    "month": 1.0,
    "monthly": 1.0,
    "per month": 1.0,
    "yr": 1.0 / 12,
    "year": 1.0 / 12,
    "yearly": 1.0 / 12,
    "annum": 1.0 / 12,
    "annual": 1.0 / 12,
    "pa": 1.0 / 12,
    "per annum": 1.0 / 12,
    "per year": 1.0 / 12,
    "hr": 160.0,
    "hour": 160.0,
    "/hr": 160.0,
    "/hour": 160.0,
    "l": 100000.0 / 12,
    "lac": 100000.0 / 12,
    "lacs": 100000.0 / 12,
    "lakh": 100000.0 / 12,
    "lakhs": 100000.0 / 12,
    "lpa": 100000.0 / 12,
}


def walk_dicts(obj: Any) -> Iterator[dict]:
    """Yield every dict encountered in a nested JSON structure (pre-order)."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_dicts(value)


def dedupe_strs(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = (item or "").strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


def parse_relative_posted(text: str) -> datetime | None:
    """Parse 'Just now', 'X days/hours/weeks/months ago' into a datetime."""
    if not text:
        return None
    t = text.lower().strip()
    now = datetime.now(timezone.utc)
    if "just now" in t or "today" in t and "ago" not in t:
        return now
    if "yesterday" in t:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\s*(day|hour|week|month|minute)s?\s*ago", t)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit == "minute":
        delta = timedelta(minutes=n)
    elif unit == "hour":
        delta = timedelta(hours=n)
    elif unit == "day":
        delta = timedelta(days=n)
    elif unit == "week":
        delta = timedelta(weeks=n)
    else:
        delta = timedelta(days=30 * n)
    return now - delta


def parse_iso_datetime(value: Any) -> datetime | None:
    """Parse ISO-ish datetime strings (naive assumed UTC) into aware datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        t = value.strip()
        if not t:
            return None
        try:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def parse_inr_salary(text: str) -> tuple[int | None, int | None]:
    """Parse Indian salary strings like '₹13,000 - 18,000 /month' or '6-8 LPA'.

    Returns (monthly_min, monthly_max) in INR.
    """
    if not text:
        return None, None
    t = text.strip()
    if any(w in t.lower() for w in ("unpaid", "not disclosed", "no salary", "negotiable")):
        return None, None

    def to_float(s: str) -> float:
        return float(s.replace(",", ""))

    def lakhish(unit: str | None) -> bool:
        return (unit or "").lower() in ("l", "lpa", "lakh", "lakhs", "lac", "lacs")

    def factor(unit: str | None) -> float:
        return _UNIT_FACTOR.get((unit or "").lower(), 1.0)

    def resolve_range(
        n1: str, u1: str | None, n2: str, u2: str | None
    ) -> tuple[float, float]:
        v1, v2 = to_float(n1), to_float(n2)
        f1, f2 = factor(u1), factor(u2)
        if u1 is None and u2 is not None:
            # A single trailing unit usually applies to both numbers, e.g.
            # '6-8 LPA'. But a large, unit-less low number (e.g. '50,000 – 1L')
            # is already an absolute monthly figure.
            if lakhish(u2) and v1 <= 100:
                f1 = f2
            elif not lakhish(u2):
                f1 = f2
        elif u2 is None and u1 is not None:
            if not lakhish(u1):
                f2 = f1
            elif v2 <= 100:
                f2 = f1
        return v1 * f1, v2 * f2

    m = _RANGE_RE.search(t)
    if m:
        lo, hi = resolve_range(m.group(1), m.group(2), m.group(3), m.group(4))
        return round(lo), round(hi)

    m = _SINGLE_RE.search(t)
    if m:
        v = to_float(m.group(1))
        lo, hi = v * factor(m.group(2)), v * factor(m.group(2))
        return round(lo), round(hi)

    nums = re.findall(rf"₹\s*{_NUM}", t)
    if nums:
        v = to_float(re.sub(r"₹", "", nums[0]).strip())
        return round(v), round(v)

    return None, None


def parse_usd_salary(text: str) -> tuple[int | None, int | None]:
    """Parse US salary strings like '$120K - $150K/yr' into monthly USD."""
    if not text or "$" not in text:
        return None, None
    t = text.replace(",", "")
    nums = re.findall(r"\d[\d]*(?:\.\d+)?", t)
    if not nums:
        return None, None
    vals = [float(n) for n in nums[:2]]
    lo, hi = vals[0], vals[1] if len(vals) > 1 else vals[0]
    if re.search(r"\d\s*[kK]", t):
        lo, hi = lo * 1000, hi * 1000
    tl = t.lower()
    if "/hr" in tl or "per hour" in tl:
        factor = 160.0
    elif "/yr" in tl or "per year" in tl or "a year" in tl or "annum" in tl:
        factor = 1.0 / 12
    else:
        factor = 1.0
    return round(lo * factor), round(hi * factor)


def parse_compensation(text: str) -> tuple[int | None, int | None, str]:
    """Parse a compensation string into (monthly_min, monthly_max, currency)."""
    if not text:
        return None, None, "INR"
    t = text.strip()
    if any(w in t.lower() for w in ("unpaid", "not disclosed", "no salary", "equity only")):
        return None, None, "INR"
    if "$" in t:
        lo, hi = parse_usd_salary(t)
        return lo, hi, "USD"
    if "€" in t:
        return None, None, "EUR"
    lo, hi = parse_inr_salary(t)
    return lo, hi, "INR"


def parse_work_mode(text: str) -> str:
    t = (text or "").lower()
    if "work from home" in t or "work-from-home" in t or "remote" in t:
        return "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "Onsite"


def parse_experience(text: str) -> str | None:
    """Extract an experience range like '2-5 yrs' from free text."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*[-–—to]+\s*(\d+)\s*(?:yrs?|years)", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{m.group(2)} yrs"
    m = re.search(r"(?:up\s*to\s*|(\d+)\s*[-+]?\s*)?(\d+)\s*(?:yrs?|years)", text, re.IGNORECASE)
    if m:
        return f"{m.group(2)} yrs"
    return None
