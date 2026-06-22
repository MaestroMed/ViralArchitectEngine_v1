"""Local LLM Service using Ollama for context-aware scoring and content generation."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMScoreResult:
    """Result from LLM scoring."""
    humor_score: float  # 0-10
    surprise_score: float  # 0-10
    hook_score: float  # 0-10
    clarity_score: float  # 0-10
    engagement_score: float  # 0-10
    reasoning: str
    tags: list[str]
    raw_response: str | None = None


@dataclass
class ContentGenerationResult:
    """Result from content generation."""
    titles: list[str]
    description: str
    hashtags: list[str]
    hook_suggestion: str | None = None


class LocalLLMService:
    """Service for local LLM inference using Ollama."""

    # Default Ollama settings (overridden by config)
    DEFAULT_MODEL = settings.LLM_MODEL if hasattr(settings, 'LLM_MODEL') else "llama3.2"
    FALLBACK_MODELS = ["llama3.1", "mistral", "phi3"]
    BASE_URL = settings.LLM_OLLAMA_URL if hasattr(settings, 'LLM_OLLAMA_URL') else "http://127.0.0.1:11434"
    TIMEOUT = float(settings.LLM_TIMEOUT if hasattr(settings, 'LLM_TIMEOUT') else 120)

    _instance: Optional["LocalLLMService"] = None
    _available: bool | None = None
    _current_model: str | None = None

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.TIMEOUT)
        )

    @classmethod
    def get_instance(cls) -> "LocalLLMService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def check_availability(self) -> bool:
        """Check if Ollama is running and has a model available."""
        if self._available is not None:
            return self._available

        try:
            response = await self.client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]

                # Find best available model
                for preferred in [self.DEFAULT_MODEL] + self.FALLBACK_MODELS:
                    if any(preferred in m for m in models):
                        self._current_model = preferred
                        self._available = True
                        logger.info(f"LLM service available with model: {self._current_model}")
                        return True

                # Use first available model
                if models:
                    self._current_model = models[0].split(":")[0]
                    self._available = True
                    logger.info(f"LLM service using model: {self._current_model}")
                    return True

                logger.warning("Ollama running but no models found")
                self._available = False
                return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False
            return False

        return False

    def is_available(self) -> bool:
        """Check cached availability status."""
        return self._available or False

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str | None:
        """Generate text using Ollama."""
        if not await self.check_availability():
            return None

        model = model or self._current_model or self.DEFAULT_MODEL

        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            if system:
                payload["system"] = system

            response = await self.client.post("/api/generate", json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                logger.error(f"Ollama error: {response.status_code} - {response.text[:200]}")
                return None

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None

    async def score_segment_context(
        self,
        transcript: str,
        duration: float,
        context: str | None = None
    ) -> LLMScoreResult | None:
        """
        Use LLM to analyze segment context and score viral potential.

        Args:
            transcript: The segment transcript text
            duration: Segment duration in seconds
            context: Optional additional context (channel name, content type, etc.)

        Returns:
            LLMScoreResult with detailed scores and reasoning
        """
        if not await self.check_availability():
            return None

        # Truncate very long transcripts
        if len(transcript) > 2000:
            transcript = transcript[:1000] + "\n...[truncated]...\n" + transcript[-500:]

        system_prompt = """Tu es un expert en contenu viral pour TikTok, YouTube Shorts et Instagram Reels.
Tu analyses des segments de stream/podcast pour évaluer leur potentiel viral.
Tu dois répondre UNIQUEMENT en JSON valide, sans texte avant ou après."""

        # Quote+escape user-controlled strings through json.dumps so a transcript
        # containing quotes / braces / newlines can't break out of the JSON
        # context and rewrite the prompt's instructions to the LLM.
        transcript_json = json.dumps(transcript, ensure_ascii=False)
        context_line = f"CONTEXTE: {json.dumps(context, ensure_ascii=False)}\n" if context else ""

        user_prompt = f"""Analyse ce segment de contenu et évalue son potentiel viral.

TRANSCRIPT ({duration:.0f}s):
{transcript_json}
{context_line}
Réponds UNIQUEMENT avec ce JSON (pas de markdown, pas de texte autour):
{{
    "humor_score": <0-10 note humour/drôle>,
    "surprise_score": <0-10 note surprise/inattendu>,
    "hook_score": <0-10 force de l'accroche>,
    "clarity_score": <0-10 compréhensible sans contexte>,
    "engagement_score": <0-10 potentiel d'engagement>,
    "reasoning": "<explication courte en français, max 100 chars>",
    "tags": ["<tag1>", "<tag2>", "<max 5 tags pertinents>"]
}}"""

        response = await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3  # Lower temperature for more consistent scoring
        )

        if not response:
            return None

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return LLMScoreResult(
                humor_score=float(data.get("humor_score", 5)),
                surprise_score=float(data.get("surprise_score", 5)),
                hook_score=float(data.get("hook_score", 5)),
                clarity_score=float(data.get("clarity_score", 5)),
                engagement_score=float(data.get("engagement_score", 5)),
                reasoning=str(data.get("reasoning", ""))[:200],
                tags=data.get("tags", [])[:5],
                raw_response=response
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response[:500]}")
            return None

    async def generate_content(
        self,
        transcript: str,
        segment_tags: list[str],
        platform: str = "tiktok"
    ) -> ContentGenerationResult | None:
        """
        Generate viral titles, descriptions, and hashtags for a clip.

        Args:
            transcript: The clip transcript
            segment_tags: Tags identified for the segment
            platform: Target platform (tiktok, youtube, instagram)

        Returns:
            ContentGenerationResult with generated content
        """
        if not await self.check_availability():
            return None

        # Truncate transcript for faster processing
        if len(transcript) > 1500:
            transcript = transcript[:750] + "\n...\n" + transcript[-500:]

        platform_hints = {
            "tiktok": "TikTok (titres courts, hashtags trending, emojis)",
            "youtube": "YouTube Shorts (titres accrocheurs, description SEO)",
            "instagram": "Instagram Reels (hashtags populaires, description engageante)"
        }

        system_prompt = """Tu es un expert en growth et marketing sur les réseaux sociaux.
Tu génères du contenu viral optimisé pour chaque plateforme.
Réponds UNIQUEMENT en JSON valide."""

        user_prompt = f"""Génère le contenu de publication pour ce clip.

PLATEFORME: {platform_hints.get(platform, platform)}

TAGS DU SEGMENT: {', '.join(segment_tags)}

TRANSCRIPT:
"{transcript[:1200]}"

Réponds UNIQUEMENT avec ce JSON:
{{
    "titles": [
        "<titre 1 - accrocheur, max 60 chars>",
        "<titre 2 - variante>",
        "<titre 3 - variante>"
    ],
    "description": "<description engageante, max 150 chars>",
    "hashtags": ["<hashtag1>", "<hashtag2>", "<5-10 hashtags pertinents>"],
    "hook_suggestion": "<phrase d'accroche pour l'intro si pertinent>"
}}"""

        response = await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.8  # Higher temperature for creative content
        )

        if not response:
            return None

        try:
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return ContentGenerationResult(
                titles=data.get("titles", [])[:5],
                description=str(data.get("description", ""))[:300],
                hashtags=data.get("hashtags", [])[:10],
                hook_suggestion=data.get("hook_suggestion")
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse content generation response: {e}")
            return None

    async def analyze_hook_quality(
        self,
        opening_text: str,
        full_transcript: str
    ) -> dict[str, Any]:
        """
        Analyze the quality of a hook/opening and suggest improvements.

        Args:
            opening_text: The first few seconds of transcript
            full_transcript: Complete transcript for context

        Returns:
            Analysis with score and suggestions
        """
        if not await self.check_availability():
            return {"available": False}

        system_prompt = """Tu analyses des accroches de vidéos virales.
Réponds UNIQUEMENT en JSON valide."""

        # See _score_segment for why we json.dumps user strings: same reason here.
        opening_json = json.dumps(opening_text, ensure_ascii=False)
        transcript_json = json.dumps(full_transcript[:800], ensure_ascii=False)
        user_prompt = f"""Analyse cette accroche de clip viral.

ACCROCHE (premiers mots):
{opening_json}

CONTEXTE COMPLET:
{transcript_json}

Réponds en JSON:
{{
    "hook_quality": <1-10>,
    "hook_type": "<question|statement|reaction|mystery|direct>",
    "strengths": ["<point fort 1>", "<point fort 2>"],
    "improvements": ["<suggestion 1>", "<suggestion 2>"],
    "alternative_hooks": ["<accroche alternative 1>", "<accroche alternative 2>"]
}}"""

        response = await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.5
        )

        if not response:
            return {"available": True, "parsed": False}

        try:
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                data["available"] = True
                data["parsed"] = True
                return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("LLM response JSON parse failed, returning raw: %s", e)

        return {"available": True, "parsed": False, "raw": response[:500]}

    async def batch_score_segments(
        self,
        segments: list[dict[str, Any]],
        max_concurrent: int = 3
    ) -> list[LLMScoreResult | None]:
        """
        Score multiple segments concurrently with rate limiting.

        Args:
            segments: List of segments with 'transcript' and 'duration' keys
            max_concurrent: Maximum concurrent LLM calls

        Returns:
            List of LLMScoreResult (or None for failed segments)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def score_with_limit(seg: dict) -> LLMScoreResult | None:
            async with semaphore:
                return await self.score_segment_context(
                    transcript=seg.get("transcript", ""),
                    duration=seg.get("duration", 60)
                )

        tasks = [score_with_limit(seg) for seg in segments]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None
        return [
            r if isinstance(r, LLMScoreResult) else None
            for r in results
        ]

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Convenience functions
async def get_llm_service() -> LocalLLMService:
    """Get the LLM service instance."""
    return LocalLLMService.get_instance()


async def is_llm_available() -> bool:
    """Check if LLM is available."""
    service = LocalLLMService.get_instance()
    return await service.check_availability()
