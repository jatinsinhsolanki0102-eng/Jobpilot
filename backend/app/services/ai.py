import json
import logging
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = None


def get_client():
    global _client
    if _client is None:
        from groq import Groq

        _client = Groq(
            api_key=settings.GROQ_API_KEY,
            timeout=settings.GROQ_TIMEOUT_SECONDS,
        )
    return _client


def ai_available() -> bool:
    return bool(settings.GROQ_API_KEY)


def chat(system: str, user: str, max_tokens: int = 2048) -> str | None:
    """Send a chat request to Groq. Returns the text response or None on failure."""
    if not ai_available():
        logger.info("GROQ_API_KEY not set; skipping AI call")
        return None
    try:
        res = get_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return res.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 - degrade gracefully to heuristics
        logger.warning("Groq call failed: %s", exc)
        return None


def chat_json(system: str, user: str, max_tokens: int = 2048) -> dict[str, Any] | None:
    """Ask the model for JSON output. Returns a dict, or None on any failure."""
    text = chat(system, user, max_tokens=max_tokens)
    if not text:
        return None
    try:
        return json.loads(extract_json(text))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Model returned non-JSON; using fallback")
        return None


def extract_json(text: str) -> str:
    """Pull the first JSON object/array out of a model response that may contain prose."""
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        raise ValueError("no JSON found")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced JSON")


def generate_cover_letter(
    candidate: dict[str, Any],
    job: dict[str, Any],
    company: str | None = None,
) -> str | None:
    """Generate a personalized cover letter. Returns None when AI is unavailable."""
    skills = ", ".join(s["name"] for s in (candidate.get("skills") or []))
    prompt = (
        f"ROLE: {job.get('title')}\n"
        f"COMPANY: {company or job.get('company_name')}\n"
        f"JOB DESCRIPTION:\n{job.get('description') or ''}\n\n"
        f"CANDIDATE SKILLS: {skills}\n"
        f"CANDIDATE PROJECTS: {json.dumps(candidate.get('projects') or [], ensure_ascii=False)[:1200]}\n"
        f"CANDIDATE EXPERIENCE: {json.dumps(candidate.get('experience') or [], ensure_ascii=False)[:1200]}\n"
        f"CANDIDATE EDUCATION: {json.dumps(candidate.get('education') or [], ensure_ascii=False)[:800]}"
    )
    text = chat(
        "You are a professional cover letter writer. Write a concise, human, ATS-friendly "
        "cover letter (3-5 short paragraphs) from this candidate to this company. Use the "
        "candidate's real skills and projects. Do not invent credentials. Sign it with the candidate name.",
        prompt,
        max_tokens=900,
    )
    return text
