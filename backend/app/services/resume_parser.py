import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .ai import chat_json

logger = logging.getLogger(__name__)

SKILL_CATEGORIES: dict[str, list[str]] = {
    "programming_languages": [
        "python",
        "java",
        "javascript",
        "typescript",
        "c++",
        "c#",
        "go",
        "golang",
        "rust",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "scala",
        "dart",
        "c",
    ],
    "frameworks": [
        "fastapi",
        "django",
        "flask",
        "react",
        "react native",
        "node.js",
        "nodejs",
        "next.js",
        "vue",
        "angular",
        "spring",
        "spring boot",
        "express",
        "laravel",
        "rails",
        "flutter",
        "tensorflow",
        "pytorch",
        "keras",
        "scikit-learn",
        "hugging face",
        "transformers",
        "spark",
        "hadoop",
        "tailwind",
        "bootstrap",
        "redux",
        "graphql",
    ],
    "databases": [
        "sql",
        "postgresql",
        "postgres",
        "mysql",
        "mongodb",
        "sqlite",
        "redis",
        "oracle",
        "elasticsearch",
        "dynamodb",
        "cassandra",
        "firebase",
        "supabase",
    ],
    "cloud": [
        "aws",
        "azure",
        "gcp",
        "google cloud",
        "docker",
        "kubernetes",
        "k8s",
        "terraform",
        "jenkins",
        "github actions",
        "serverless",
        "vercel",
        "heroku",
        "cloudflare",
    ],
    "data_science": [
        "machine learning",
        "deep learning",
        "nlp",
        "computer vision",
        "data science",
        "data analysis",
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "llm",
        "rag",
        "ai",
        "artificial intelligence",
        "llmops",
        "prompt engineering",
    ],
    "tools": [
        "git",
        "github",
        "gitlab",
        "jira",
        "docker",
        "pytest",
        "selenium",
        "playwright",
        "postman",
        "linux",
        "bash",
        "power bi",
        "tableau",
        "excel",
        "figma",
    ],
    "soft_skills": [
        "communication",
        "teamwork",
        "leadership",
        "problem solving",
        "critical thinking",
        "time management",
        "collaboration",
        "adaptability",
        "creativity",
        "presentation",
        "mentoring",
        "project management",
        "agile",
        "scrum",
    ],
}

CATEGORY_LABELS = {
    "programming_languages": "Languages",
    "frameworks": "Frameworks",
    "databases": "Databases",
    "cloud": "Cloud & DevOps",
    "data_science": "AI & Data",
    "tools": "Tools",
    "soft_skills": "Soft Skills",
}

PARSE_SYSTEM_PROMPT = """You are a resume parser. Extract structured data from the resume text.
Return ONLY valid JSON matching this schema:
{
  "full_name": string | null,
  "email": string | null,
  "phone": string | null,
  "location": string | null,
  "summary": string | null,
  "skills": [{"name": string, "category": "Languages|Frameworks|Databases|Cloud & DevOps|AI & Data|Tools|Soft Skills|Other"}],
  "experience": [{"role": string, "company": string, "start": string | null, "end": string | null, "bullets": [string]}],
  "projects": [{"name": string, "description": string, "technologies": [string]}],
  "education": [{"degree": string, "institution": string, "year": string | null, "cgpa": string | null}],
  "certifications": [string],
  "career_goals": string | null
}
Do not invent facts. Use empty lists when a section is missing."""


@dataclass
class ParsedResume:
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    skills: list[dict[str, str]] = field(default_factory=list)
    experience: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    career_goals: str | None = None
    raw_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "summary": self.summary,
            "skills": self.skills,
            "experience": self.experience,
            "projects": self.projects,
            "education": self.education,
            "certifications": self.certifications,
            "career_goals": self.career_goals,
        }


def extract_text_from_pdf(data: bytes) -> str:
    import fitz

    text_parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(str(page.get_text("text")))
    return clean_text("\n".join(text_parts))


def extract_text_from_txt(data: bytes) -> str:
    return clean_text(data.decode("utf-8", errors="ignore"))


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_resume(data: bytes, file_type: str) -> ParsedResume:
    if file_type == "pdf":
        raw = extract_text_from_pdf(data)
    else:
        raw = extract_text_from_txt(data)

    parsed = _parse_with_ai(raw)
    if parsed is None:
        parsed = parse_heuristic(raw)
    parsed = _merge_heuristic(raw, parsed)
    parsed.raw_text = raw
    return parsed


def _parse_with_ai(raw: str) -> ParsedResume | None:
    data = chat_json(
        PARSE_SYSTEM_PROMPT,
        f"Resume text:\n\n{raw[:14000]}",
        max_tokens=2500,
    )
    if not data:
        return None
    return ParsedResume(
        full_name=data.get("full_name"),
        email=data.get("email"),
        phone=data.get("phone"),
        location=data.get("location"),
        summary=data.get("summary"),
        skills=data.get("skills", [])
        if isinstance(data.get("skills", []), list)
        else [],
        experience=data.get("experience", [])
        if isinstance(data.get("experience", []), list)
        else [],
        projects=data.get("projects", [])
        if isinstance(data.get("projects", []), list)
        else [],
        education=data.get("education", [])
        if isinstance(data.get("education", []), list)
        else [],
        certifications=data.get("certifications", [])
        if isinstance(data.get("certifications", []), list)
        else [],
        career_goals=data.get("career_goals"),
    )


def _merge_heuristic(raw: str, parsed: ParsedResume) -> ParsedResume:
    """Fill any gaps left by the AI with the deterministic extractor."""
    heur = _extract_heuristic(raw)
    if not parsed.email:
        parsed.email = heur.email
    if not parsed.phone:
        parsed.phone = heur.phone
    if not parsed.location:
        parsed.location = heur.location

    known = {s["name"].lower() for s in parsed.skills}
    for s in heur.skills:
        if s["name"].lower() not in known:
            parsed.skills.append(s)
            known.add(s["name"].lower())
    return parsed


def parse_heuristic(raw: str) -> ParsedResume:
    return _extract_heuristic(raw)


def _extract_heuristic(raw: str) -> ParsedResume:
    text = raw.lower()
    skills = _extract_skills(text)
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw)
    phone = re.search(r"(?:\+?\d[\d\s\-()]{8,})", raw)
    parsed = ParsedResume(
        email=email.group(0) if email else None,
        phone=phone.group(0).strip() if phone else None,
        skills=skills,
        experience=_extract_experience_sections(raw),
        projects=_extract_projects_sections(raw),
        education=_extract_education_sections(raw),
        certifications=_extract_certifications_sections(raw),
    )
    return parsed


def _extract_skills(text: str) -> list[dict[str, str]]:
    found: dict[str, list[str]] = {}
    for category, names in SKILL_CATEGORIES.items():
        for name in names:
            if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
                found.setdefault(category, []).append(name.title())
    result: list[dict[str, str]] = []
    for category, names in found.items():
        for name in names:
            result.append({"name": name, "category": CATEGORY_LABELS[category]})
    return result


def _split_sections(raw: str) -> dict[str, str]:
    section_headers = {
        "experience": r"(work experience|professional experience|employment history|experience)",
        "projects": r"(projects|personal projects|key projects|academic projects)",
        "education": r"(education|academic qualifications|academics)",
        "certifications": r"(certifications|certificates|courses)",
        "skills": r"(technical skills|skills|core competencies)",
    }
    lines = raw.splitlines()
    current = "other"
    sections: dict[str, list[str]] = {
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "skills": [],
        "other": [],
    }
    for line in lines:
        lower = line.strip().lower()
        matched = None
        for key, pattern in section_headers.items():
            if re.fullmatch(rf"[\s#>*\-]*{pattern}[\s:]*", lower):
                matched = key
                break
        if matched:
            current = matched
            continue
        sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def _extract_experience_sections(raw: str) -> list[dict[str, Any]]:
    sections = _split_sections(raw)
    body = sections["experience"].split("\n")
    result: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        if (
            re.search(r"^\s*(?:[A-Z][\w&\- ]{2,40})\s*[|,]\s*[A-Z]", stripped)
            and len(stripped) < 90
        ):
            if current:
                result.append(current)
            parts = re.split(r"\s*[|,]\s*", stripped, maxsplit=1)
            current = {
                "role": parts[0].strip(),
                "company": parts[1].strip() if len(parts) > 1 else "",
                "start": None,
                "end": None,
                "bullets": [],
            }
        elif current and stripped.startswith(("-", "•", "*")):
            current["bullets"].append(stripped.lstrip("-•* ").strip())
        elif current:
            current["bullets"].append(stripped)
    if current:
        result.append(current)
    return result


def _extract_projects_sections(raw: str) -> list[dict[str, Any]]:
    sections = _split_sections(raw)
    body = sections["projects"].split("\n")
    result: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < 80 and not stripped.startswith(("-", "•", "*")):
            if current:
                result.append(current)
            current = {"name": stripped, "description": "", "technologies": []}
        elif current and stripped.startswith(("-", "•", "*")):
            content = stripped.lstrip("-•* ").strip()
            if current["description"]:
                current["description"] += " "
            current["description"] += content
    if current:
        result.append(current)
    return result


def _extract_education_sections(raw: str) -> list[dict[str, Any]]:
    sections = _split_sections(raw)
    body = sections["education"].split("\n")
    result: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) > 0:
            if current:
                result.append(current)
            cgpa = re.search(r"(?:CGPA|cpi)[:\s]*([\d.]+)/?10", stripped, re.IGNORECASE)
            degree_year = re.search(r"(20\d\d|19\d\d)", stripped)
            current = {
                "degree": stripped,
                "institution": "",
                "year": degree_year.group(1) if degree_year else None,
                "cgpa": cgpa.group(1) if cgpa else None,
            }
    if current:
        result.append(current)
    return result


def _extract_certifications_sections(raw: str) -> list[str]:
    sections = _split_sections(raw)
    body = sections["certifications"].split("\n")
    certs: list[str] = []
    for line in body:
        stripped = line.strip().lstrip("-•* ")
        if stripped and len(stripped) < 120:
            certs.append(stripped)
    return certs
