"""Main API router for v1."""

from fastapi import APIRouter

from forge_engine.api.v1.endpoints import projects, jobs, templates, profiles, capabilities, thumbnails, websockets, channels, monitor

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])
api_router.include_router(channels.router, prefix="/channels", tags=["Channels"])
api_router.include_router(capabilities.router, tags=["System"])
api_router.include_router(thumbnails.router, tags=["Thumbnails"])
api_router.include_router(websockets.router, tags=["Real-time"])
api_router.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])





