import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .ai import ai_available, chat_json

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#.]{1,}")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


class TfidfVectorizer:
    """Small pure-python TF-IDF vectorizer (no heavy dependencies)."""

    def __init__(self) -> None:
        self.idf: dict[str, float] = {}
        self.vocab: list[str] = []

    def fit(self, corpus: list[str]) -> "TfidfVectorizer":
        n_docs = len(corpus)
        df: Counter[str] = Counter()
        for doc in corpus:
            df.update(set(tokenize(doc)))
        self.idf = {
            term: math.log((1 + n_docs) / (1 + count)) + 1.0
            for term, count in df.items()
        }
        self.vocab = sorted(self.idf)
        return self

    def transform(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        total = sum(counts.values()) or 1
        return {
            t: (c / total) * self.idf[t] for t, c in counts.items() if t in self.idf
        }


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(ak * b.get(k, 0.0) for k, ak in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _skill_names(resume_skills: list[dict[str, Any]] | None) -> set[str]:
    out: set[str] = set()
    for s in resume_skills or []:
        name = (s.get("name") or "").lower()
        if name:
            out.add(name)
    return out


def _job_skill_names(job_skills: list[str] | None) -> set[str]:
    out: set[str] = set()
    for s in job_skills or []:
        name = str(s).lower().strip()
        if name:
            out.add(name)
    return out


def _skill_match_score(
    resume_skills: list[dict[str, Any]] | None, job_skills: list[str] | None
) -> float:
    """0..1 weighted overlap: required skills matter more than nice-to-haves."""
    resume = _skill_names(resume_skills)
    job = _job_skill_names(job_skills)
    if not job:
        return 0.5
    matched = resume & job
    return len(matched) / len(job)


def _compute_semantic(resume_text: str, jobs: list[dict[str, Any]]) -> dict[int, float]:
    corpus = [resume_text] + [
        (j.get("description") or j.get("title") or "") for j in jobs
    ]
    vectorizer = TfidfVectorizer().fit(corpus)
    resume_vec = vectorizer.transform(resume_text)
    scores: dict[int, float] = {}
    for j in jobs:
        doc = (
            (j.get("description") or "")
            + " "
            + (j.get("title") or "")
            + " "
            + (j.get("skills_required") and " ".join(j["skills_required"]) or "")
        )
        scores[j["id"]] = cosine(resume_vec, vectorizer.transform(doc))
    return scores


def match_scores(
    resume_text: str,
    resume_skills: list[dict[str, Any]] | None,
    jobs: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Deterministic semantic + skill matching. Returns per-job score breakdown."""
    semantic = _compute_semantic(resume_text, jobs)
    results: dict[int, dict[str, Any]] = {}
    for j in jobs:
        skill = _skill_match_score(resume_skills, j.get("skills_required"))
        sem = semantic.get(j["id"], 0.0)
        overall = 0.6 * skill + 0.4 * sem
        results[j["id"]] = {
            "score": round(min(100.0, overall * 100), 1),
            "skill_match": round(skill * 100, 1),
            "semantic_match": round(sem * 100, 1),
            "matched_skills": sorted(
                _skill_names(resume_skills) & _job_skill_names(j.get("skills_required"))
            ),
            "missing_skills": sorted(
                _job_skill_names(j.get("skills_required")) - _skill_names(resume_skills)
            ),
        }
    return results


def preference_fit(pref: dict[str, Any] | None, job: dict[str, Any]) -> float:
    """0..1 score for how well a job fits the user's stated preferences."""
    if not pref:
        return 0.5
    checks: list[float] = []

    job_type = job.get("employment_type") or ""
    pref_type = pref.get("job_type")
    if pref_type:
        checks.append(1.0 if pref_type.lower() in job_type.lower() else 0.4)

    work_modes = pref.get("work_modes") or []
    job_mode = (job.get("work_mode") or "").lower()
    if work_modes:
        if not job_mode:
            checks.append(0.5)
        elif job_mode in [w.lower() for w in work_modes]:
            checks.append(1.0)
        else:
            checks.append(0.0)

    locations = pref.get("locations") or []
    job_loc = (job.get("location") or "").lower()
    if locations:
        if not job_loc:
            checks.append(0.5)
        elif (
            any(loc.lower() in job_loc for loc in locations)
            or "remote" in job_loc
            and "remote" in [w.lower() for w in work_modes]
        ):
            checks.append(1.0)
        else:
            checks.append(0.2)

    salary_min = pref.get("salary_min")
    job_salary = job.get("salary_max") or job.get("salary_min")
    if salary_min and job_salary:
        checks.append(1.0 if job_salary >= salary_min else 0.3)

    domains = pref.get("domains") or []
    if domains:
        haystack = (
            (job.get("title") or "").lower()
            + " "
            + (job.get("description") or "").lower()
            + " "
            + " ".join(str(s) for s in (job.get("skills_required") or [])).lower()
        )
        checks.append(1.0 if any(d.lower() in haystack for d in domains) else 0.3)

    return sum(checks) / len(checks) if checks else 0.5


def freshness_factor(job: dict[str, Any]) -> float:
    posted = job.get("posted_at") or job.get("created_at")
    if not posted:
        return 0.6
    if isinstance(posted, str):
        try:
            posted = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        except ValueError:
            return 0.6
    now = datetime.now(timezone.utc)
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    age_days = (now - posted).days
    if age_days < 7:
        return 1.0
    if age_days < 30:
        return 0.8
    return 0.5


def rank_jobs(
    resume_text: str,
    resume_skills: list[dict[str, Any]] | None,
    pref: dict[str, Any] | None,
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Recommendation engine: combine match score, preference fit, and freshness."""
    scores = match_scores(resume_text, resume_skills, jobs)
    ranked: list[dict[str, Any]] = []
    for j in jobs:
        ms = scores[j["id"]]
        fit = preference_fit(pref, j)
        fresh = freshness_factor(j)
        final = 0.6 * (ms["score"] / 100) + 0.3 * fit + 0.1 * fresh
        ranked.append(
            {
                **j,
                "match": ms,
                "preference_fit": round(fit * 100, 1),
                "rank_score": round(final * 100, 1),
            }
        )
    ranked.sort(key=lambda x: x["rank_score"], reverse=True)
    return ranked


def ai_match_score(
    resume_text: str, resume_skills: list[dict[str, Any]] | None, job: dict[str, Any]
) -> dict[str, Any] | None:
    """Optional LLM assessment of a single resume/job pair. Returns None when unavailable."""
    if not ai_available():
        return None
    skills = ", ".join(s["name"] for s in (resume_skills or []))
    prompt = (
        f"JOB TITLE: {job.get('title')}\n"
        f"COMPANY: {job.get('company_name')}\n"
        f"REQUIRED SKILLS: {', '.join(str(s) for s in (job.get('skills_required') or []))}\n"
        f"JOB DESCRIPTION:\n{job.get('description') or ''}\n\n"
        f"CANDIDATE SKILLS: {skills}\n\n"
        f"CANDIDATE RESUME:\n{resume_text[:5000]}"
    )
    data = chat_json(
        "You are a recruiting assistant. Assess how well this candidate matches the job. "
        'Return ONLY JSON: {"score": int 0-100, "strengths": [string], "gaps": [string], "summary": string}',
        prompt,
        max_tokens=700,
    )
    if not data:
        return None
    return {
        "score": max(0, min(100, int(data.get("score", 50)))),
        "strengths": data.get("strengths", []),
        "gaps": data.get("gaps", []),
        "summary": data.get("summary"),
    }
