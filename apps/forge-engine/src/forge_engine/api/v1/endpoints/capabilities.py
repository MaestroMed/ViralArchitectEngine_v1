"""System capabilities endpoint."""

import shutil
from pathlib import Path

from fastapi import APIRouter

from forge_engine.core.config import settings
from forge_engine.services.ffmpeg import FFmpegService
from forge_engine.services.transcription import TranscriptionService

router = APIRouter()


@router.get("/capabilities")
async def get_capabilities() -> dict:
    """Get system capabilities."""
    ffmpeg = FFmpegService()
    transcription = TranscriptionService()
    
    # Check FFmpeg
    ffmpeg_available = await ffmpeg.check_availability()
    ffmpeg_info = {
        "version": ffmpeg.version or "unknown",
        "hasNvenc": ffmpeg.has_nvenc,
        "hasLibass": ffmpeg.has_libass,
        "encoders": ffmpeg.available_encoders,
    } if ffmpeg_available else {
        "version": "not found",
        "hasNvenc": False,
        "hasLibass": False,
        "encoders": [],
    }
    
    # Check Whisper - get actual device info via ctranslate2 (what faster-whisper actually uses)
    whisper_device = "cpu"
    whisper_compute_type = "float32"
    cuda_available = False
    
    try:
        import ctranslate2
        cuda_count = ctranslate2.get_cuda_device_count()
        if cuda_count > 0:
            cuda_available = True
            whisper_device = "cuda"
            whisper_compute_type = settings.WHISPER_COMPUTE_TYPE
    except (ImportError, Exception):
        pass
    
    # Fallback to torch if available
    if not cuda_available:
        try:
            import torch
            if torch.cuda.is_available():
                whisper_device = "cuda"
                whisper_compute_type = settings.WHISPER_COMPUTE_TYPE
        except ImportError:
            pass
    
    # Check if model is loaded (singleton check)
    model_loaded = False
    try:
        singleton_transcription = TranscriptionService.get_instance() if hasattr(TranscriptionService, 'get_instance') else transcription
        model_loaded = singleton_transcription._model is not None if hasattr(singleton_transcription, '_model') else False
    except Exception:
        pass
    
    whisper_info = {
        "available": transcription.is_available(),
        "models": ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        "currentModel": settings.WHISPER_MODEL,
        "device": whisper_device,
        "computeType": whisper_compute_type,
        "modelLoaded": model_loaded,
    }
    
    # Check GPU via CTranslate2 (used by faster-whisper)
    gpu_info = {"available": False, "name": None, "memory": None}
    try:
        import ctranslate2
        cuda_count = ctranslate2.get_cuda_device_count()
        if cuda_count > 0:
            # Try to get GPU name via subprocess
            gpu_name = "NVIDIA GPU"
            try:
                import subprocess
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    gpu_name = result.stdout.strip().split('\n')[0]
            except Exception:
                pass
            
            gpu_info = {
                "available": True,
                "name": gpu_name,
                "memory": None,  # CTranslate2 doesn't expose memory info
            }
    except ImportError:
        pass
    
    # Storage info
    library_path = Path(settings.LIBRARY_PATH)
    try:
        usage = shutil.disk_usage(library_path)
        storage_info = {
            "libraryPath": str(library_path),
            "freeSpace": usage.free,
        }
    except Exception:
        storage_info = {
            "libraryPath": str(library_path),
            "freeSpace": 0,
        }
    
    return {
        "ffmpeg": ffmpeg_info,
        "whisper": whisper_info,
        "gpu": gpu_info,
        "storage": storage_info,
    }


