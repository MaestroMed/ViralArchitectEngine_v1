"""FORGE Engine services."""

from forge_engine.services.ffmpeg import FFmpegService
from forge_engine.services.transcription import TranscriptionService
from forge_engine.services.ingest import IngestService

# Lazy imports for services requiring optional dependencies
def get_analysis_service():
    from forge_engine.services.analysis import AnalysisService
    return AnalysisService

def get_virality_scorer():
    from forge_engine.services.virality import ViralityScorer
    return ViralityScorer

def get_layout_engine():
    from forge_engine.services.layout import LayoutEngine
    return LayoutEngine

def get_caption_engine():
    from forge_engine.services.captions import CaptionEngine
    return CaptionEngine

def get_render_service():
    from forge_engine.services.render import RenderService
    return RenderService

def get_export_service():
    from forge_engine.services.export import ExportService
    return ExportService

__all__ = [
    "FFmpegService",
    "TranscriptionService",
    "IngestService",
    "get_analysis_service",
    "get_virality_scorer",
    "get_layout_engine",
    "get_caption_engine",
    "get_render_service",
    "get_export_service",
]
