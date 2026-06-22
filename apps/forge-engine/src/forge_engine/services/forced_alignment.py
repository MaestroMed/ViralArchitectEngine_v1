"""Forced alignment of whisper word timings (torchaudio MMS_FA, CPU).

faster-whisper's word timestamps are decoder-attention estimates (~50-150ms drift,
worse on fast speech). That loose timing is the shared ceiling under animated
captions (the karaoke highlight lands off-syllable) and peak-anchored cold-opens.

This snaps each word to wav2vec2/CTC frame boundaries (±20-50ms) using
``torchaudio.functional.forced_align`` + the bundled ``MMS_FA`` pipeline — which
runs on the INSTALLED torch 2.12 / torchaudio 2.11 with NO downgrade, no whisperx,
no new deps (the WhisperX path was deferred precisely because it downgrades torch).
Measured ~17x realtime on CPU. Keeps faster-whisper as the TEXT model; only the
timings change.

Off by default (FORGE_FORCED_ALIGN) — see the per-segment cost note in
align_transcription. Mirrors WhisperXAligner.align_transcription so it's a drop-in.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import unicodedata
from typing import Any, Callable

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


class ForcedAligner:
    """Singleton CTC forced-aligner. Lazy-loads the MMS_FA model on first use."""

    _instance: "ForcedAligner | None" = None

    def __init__(self) -> None:
        self._model = None
        self._dictionary: dict[str, int] | None = None
        self._sample_rate = 16000
        self._available: bool | None = None

    @classmethod
    def get_instance(cls) -> "ForcedAligner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        """True if torchaudio + the MMS_FA forced-align stack import on this box."""
        if self._available is not None:
            return self._available
        try:
            import torchaudio  # noqa: F401
            from torchaudio.functional import forced_align  # noqa: F401
            from torchaudio.pipelines import MMS_FA  # noqa: F401
            self._available = True
        except Exception as e:  # noqa: BLE001
            logger.info("Forced alignment unavailable (%s) — keeping whisper timings", e)
            self._available = False
        return self._available

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from torchaudio.pipelines import MMS_FA as bundle
        self._model = bundle.get_model().eval()
        self._dictionary = bundle.get_dict()
        self._sample_rate = bundle.sample_rate

    # ── audio ────────────────────────────────────────────────────────────────
    def _load_audio(self, audio_path: str):
        """Decode any audio to 16k mono float32 via ffmpeg (avoids torchaudio.load,
        which now routes through torchcodec that isn't installed)."""
        import numpy as np

        ff = getattr(settings, "FFMPEG_PATH", None) or "ffmpeg"
        proc = subprocess.run(
            [str(ff), "-v", "error", "-i", audio_path, "-ac", "1",
             "-ar", str(self._sample_rate), "-f", "s16le", "-"],
            capture_output=True,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise RuntimeError(f"ffmpeg PCM decode failed rc={proc.returncode}")
        return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0

    def _tokenize(self, word: str) -> list[int]:
        """Romanize a word into the MMS char dict (lowercase, strip accents/punct)."""
        w = unicodedata.normalize("NFKD", word.lower())
        w = "".join(c for c in w if not unicodedata.combining(c))
        w = re.sub(r"[^a-z']", "", w)
        d = self._dictionary or {}
        return [d[c] for c in w if c in d]

    # ── public API (mirrors WhisperXAligner) ──────────────────────────────────
    async def align_transcription(
        self,
        audio_path: str,
        transcription: dict[str, Any],
        language: str | None = None,
        progress_callback: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Return the transcription with word ``start``/``end`` snapped to CTC
        frames. Aligns per whisper segment (bounded memory, local word→audio
        match). Best-effort: on any failure the original timings are kept, and a
        segment that can't be aligned is left untouched.

        Cost: roughly realtime/17 of total speech, run once after transcribe. For
        a multi-hour VOD prefer aligning per CLIP at export instead (~5s/clip)."""
        if not self.is_available():
            return transcription
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._align_sync(audio_path, transcription, progress_callback)
        )

    def _align_sync(
        self,
        audio_path: str,
        transcription: dict[str, Any],
        progress_callback: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        import numpy as np
        import torch
        from torchaudio.functional import forced_align, merge_tokens

        try:
            self._ensure_model()
            audio = self._load_audio(audio_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Forced alignment setup failed (%s) — keeping whisper timings", e)
            return transcription

        sr = self._sample_rate
        segments = transcription.get("segments", []) or []
        aligned_words = 0
        for si, seg in enumerate(segments):
            words = seg.get("words") or []
            if not words:
                continue
            s0 = float(seg.get("start", 0.0))
            s1 = float(seg.get("end", s0))
            a = audio[int(s0 * sr): int(s1 * sr)]
            if a.size < sr // 50:  # < 20ms of audio
                continue
            tokenized = [self._tokenize(w.get("word", "")) for w in words]
            flat = [t for toks in tokenized for t in toks]
            if not flat:
                continue
            try:
                wav = torch.from_numpy(a).unsqueeze(0)
                with torch.inference_mode():
                    emission, _ = self._model(wav)
                    targets = torch.tensor([flat], dtype=torch.int32)
                    # CTC needs at least as many frames as target tokens.
                    if emission.shape[1] < targets.shape[1]:
                        continue
                    aligned_tokens, scores = forced_align(emission, targets, blank=0)
                spans = merge_tokens(aligned_tokens[0], scores[0])
                ratio = wav.shape[1] / emission.shape[1] / sr
            except Exception as e:  # noqa: BLE001
                logger.debug("Segment %d alignment skipped: %s", si, e)
                continue

            idx = 0
            for w, toks in zip(words, tokenized):
                n = len(toks)
                if n == 0 or idx + n > len(spans):
                    idx += n
                    continue
                wspans = spans[idx: idx + n]
                idx += n
                w["start"] = round(s0 + wspans[0].start * ratio, 3)
                w["end"] = round(s0 + wspans[-1].end * ratio, 3)
                aligned_words += 1

            if progress_callback and segments:
                progress_callback(min(100, int((si + 1) / len(segments) * 100)))

        transcription["alignment_method"] = "torchaudio_mms_fa"
        logger.info("✓ Forced alignment: %d words snapped to CTC frames", aligned_words)
        return transcription
