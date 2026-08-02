from fastapi import APIRouter

from . import (
    analytics,
    applications,
    auth,
    dashboard,
    jobs,
    notifications,
    preferences,
    resumes,
    saved,
    telegram,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(resumes.router)
api_router.include_router(preferences.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(dashboard.router)
api_router.include_router(notifications.router)
api_router.include_router(telegram.router)
api_router.include_router(analytics.router)
api_router.include_router(saved.router)
