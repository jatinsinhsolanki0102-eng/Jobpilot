from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_jobs: int
    applied: int
    pending: int
    interviews: int
    offers: int
    rejected: int
    saved: int
    top_matches: list[dict] = []
    recent_applications: list[dict] = []
    top_skills: list[dict] = []
