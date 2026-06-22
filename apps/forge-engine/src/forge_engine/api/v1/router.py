"""Main API router for v1."""

from fastapi import APIRouter

from forge_engine.api.v1.endpoints import (
    analytics,
    api_keys,
    assistant,
    audio,
    capabilities,
    channels,
    clips_mobile,
    compilation,
    content,
    dictionaries,
    emotion,
    jobs,
    llm,
    ml_scoring,
    monitor,
    profiles,
    projects,
    reviews,
    social,
    templates,
    thumbnails,
    translation,
    virality,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])
api_router.include_router(channels.router, prefix="/channels", tags=["Channels"])
api_router.include_router(dictionaries.router, tags=["Dictionaries"])
api_router.include_router(capabilities.router, tags=["System"])
api_router.include_router(thumbnails.router, tags=["Thumbnails"])
# NOTE: websockets.router is intentionally NOT included here. WS handshakes
# can't be gated by the global Depends(require_api_key) (Header dependency)
# cleanly, so it is mounted separately in main.py and self-authenticates via
# authorize_websocket(). See main.py and core/auth.py.
api_router.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])
api_router.include_router(llm.router, prefix="/llm", tags=["AI/LLM"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["AI Assistant"])

# New AI/ML endpoints
api_router.include_router(emotion.router, prefix="/emotion", tags=["Emotion Detection"])
api_router.include_router(audio.router, prefix="/audio", tags=["Audio Analysis"])
api_router.include_router(ml_scoring.router, prefix="/ml-scoring", tags=["ML Scoring"])
api_router.include_router(content.router, prefix="/content", tags=["Content Generation"])
api_router.include_router(translation.router, prefix="/translation", tags=["Translation"])
api_router.include_router(virality.router, prefix="/virality", tags=["Virality Prediction"])
api_router.include_router(compilation.router, prefix="/compilation", tags=["Compilation"])
api_router.include_router(social.router, prefix="/social", tags=["Social Publishing"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(reviews.router, prefix="/clips", tags=["Clip Review & Queue"])
api_router.include_router(clips_mobile.router, prefix="/clips", tags=["Clips (mobile)"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])





