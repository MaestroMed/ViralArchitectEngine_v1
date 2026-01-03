"""Test Whisper transcription."""
import asyncio
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from forge_engine.services.transcription import TranscriptionService

async def test():
    svc = TranscriptionService()
    print(f'Whisper available: {svc.is_available()}')
    print(f'Device: {svc.device}')
    
    audio = r'C:\Users\Matter1\FORGE_LIBRARY\projects\2489b099-2589-4a38-aaf9-4985f2a68826\analysis\audio.wav'
    print('Testing transcription...')
    
    try:
        result = await svc.transcribe(audio, language='fr', word_timestamps=True)
        segments = result.get("segments", [])
        print(f'SUCCESS! Got {len(segments)} segments')
        if segments:
            print(f'First segment: {segments[0]["text"][:100]}')
    except Exception as e:
        print(f'FAILED: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
