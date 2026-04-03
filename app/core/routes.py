"""
Router Registration Module
==========================
Centralizes API router inclusion.

Author: Political Communication Platform Team
"""

from fastapi import FastAPI

from app.core.config import settings

from app.api.routes import (
    auth,
    users,
    complaints,
    appointments,
    events,
    polls,
    feedback,
    announcements,
    notifications,
    analytics,
    voter_profile,
    areas,
    wards,
)
from app.api.routes import help_numbers as help_numbers_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.chat import router as chat_router


def register_routers(app: FastAPI) -> None:
    """
    Register all API routers on the FastAPI app instance.
    """
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["Authentication"])
    # Backward compatibility: allow /auth/* without /api/v1 prefix
    app.include_router(auth.router, tags=["Authentication (Legacy)"])
    app.include_router(users.router, prefix=settings.API_V1_PREFIX, tags=["Users"])
    app.include_router(announcements.router, prefix=settings.API_V1_PREFIX, tags=["Announcements"])
    app.include_router(polls.router, prefix=settings.API_V1_PREFIX, tags=["Polls"])
    app.include_router(complaints.router, prefix=settings.API_V1_PREFIX, tags=["Complaints"])
    app.include_router(appointments.router, prefix=settings.API_V1_PREFIX, tags=["Appointments"])
    app.include_router(events.router, prefix=settings.API_V1_PREFIX, tags=["Events"])
    app.include_router(feedback.router, prefix=settings.API_V1_PREFIX, tags=["Feedback"])
    app.include_router(notifications.router, prefix=settings.API_V1_PREFIX, tags=["Notifications"])
    app.include_router(analytics.router, prefix=settings.API_V1_PREFIX, tags=["Analytics"])
    app.include_router(voter_profile.router, prefix=settings.API_V1_PREFIX, tags=["Voter Profile"])
    app.include_router(chat_router, prefix=settings.API_V1_PREFIX, tags=["Chat"])
    app.include_router(help_numbers_router.router, prefix=settings.API_V1_PREFIX, tags=["Help Numbers"])
    app.include_router(campaigns_router, prefix=settings.API_V1_PREFIX, tags=["Campaigns"])
    app.include_router(areas.router, prefix=settings.API_V1_PREFIX, tags=["Areas"])
    app.include_router(wards.router, prefix=settings.API_V1_PREFIX, tags=["Wards"])
