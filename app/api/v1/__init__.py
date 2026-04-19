"""
PhishLens API v1 Router Package

Aggregates all API route modules.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    scenarios,
    templates,
    generations,
    campaigns,
    admin,
    export,
    bulk_generations,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["Scenarios"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(
    generations.router, prefix="/generations", tags=["Generations"]
)
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])
api_router.include_router(bulk_generations.router)
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
