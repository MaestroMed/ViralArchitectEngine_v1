"""Dictionary service for transcript correction and Whisper prompting."""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default dictionaries directory
DICTIONARIES_DIR = Path(__file__).parent.parent / "dictionaries"


class DictionaryService:
    """Service for loading and applying custom dictionaries."""

    _instance = None
    _dictionaries: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "DictionaryService":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_all_dictionaries()
        return cls._instance

    def _load_all_dictionaries(self) -> None:
        """Load all dictionaries from the dictionaries folder."""
        if not DICTIONARIES_DIR.exists():
            logger.warning(f"Dictionaries directory not found: {DICTIONARIES_DIR}")
            return

        for file in DICTIONARIES_DIR.glob("*.json"):
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
                    name = file.stem
                    self._dictionaries[name] = data
                    logger.info(f"[Dictionary] Loaded: {name} ({len(data.get('corrections', {}))} corrections, {len(data.get('hotwords', []))} hotwords)")
            except Exception as e:
                logger.error(f"[Dictionary] Failed to load {file}: {e}")

    def list_dictionaries(self) -> list[dict[str, str]]:
        """List all available dictionaries."""
        return [
            {
                "id": name,
                "name": data.get("name", name),
                "description": data.get("description", ""),
                "author": data.get("author", ""),
                "corrections_count": len(data.get("corrections", {})),
                "hotwords_count": len(data.get("hotwords", [])),
            }
            for name, data in self._dictionaries.items()
        ]

    def get_dictionary(self, name: str) -> dict[str, Any] | None:
        """Get a dictionary by name."""
        return self._dictionaries.get(name)

    def get_whisper_prompt(self, dictionary_name: str) -> str | None:
        """Get the Whisper initial prompt for a dictionary."""
        dict_data = self._dictionaries.get(dictionary_name)
        if dict_data:
            return dict_data.get("whisper_prompt")
        return None

    def get_hotwords(self, dictionary_name: str) -> list[str]:
        """Get hotwords for a dictionary."""
        dict_data = self._dictionaries.get(dictionary_name)
        if dict_data:
            return dict_data.get("hotwords", [])
        return []

    def apply_corrections(
        self,
        text: str,
        dictionary_name: str,
        case_sensitive: bool = False
    ) -> str:
        """Apply dictionary corrections to text."""
        dict_data = self._dictionaries.get(dictionary_name)
        if not dict_data:
            return text

        corrections = dict_data.get("corrections", {})
        if not corrections:
            return text

        result = text

        # Sort by length (longest first) to avoid partial replacements
        sorted_corrections = sorted(
            corrections.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        for wrong, correct in sorted_corrections:
            if not wrong:
                continue
            # WHOLE-WORD match only. A bare substring sub mangles ordinary words:
            # an "ez"->"EZ" hotword turns "avez"->"avEZ", "gardé"->"Guardian…" etc.
            # Anchor \b only on edges that are word chars (\b is Unicode-aware in
            # Py3 str regex, so it respects accented French letters), leaving
            # symbol-y entries like "C+" able to match.
            lb = r"\b" if (wrong[0].isalnum() or wrong[0] == "_") else ""
            rb = r"\b" if (wrong[-1].isalnum() or wrong[-1] == "_") else ""
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(rf"{lb}{re.escape(wrong)}{rb}", flags)
            result = pattern.sub(correct, result)

        return result

    def apply_corrections_to_words(
        self,
        words: list[dict[str, Any]],
        dictionary_name: str
    ) -> list[dict[str, Any]]:
        """Apply dictionary corrections to word timings."""
        dict_data = self._dictionaries.get(dictionary_name)
        if not dict_data:
            return words

        corrections = dict_data.get("corrections", {})
        if not corrections:
            return words

        # Build lowercase lookup
        corrections_lower = {k.lower(): v for k, v in corrections.items()}

        corrected_words = []
        for word_data in words:
            word = word_data.get("word", "")
            word_lower = word.lower().strip()

            # Check for exact match
            if word_lower in corrections_lower:
                corrected_words.append({
                    **word_data,
                    "word": corrections_lower[word_lower],
                    "original": word,  # Keep original for reference
                })
            else:
                corrected_words.append(word_data)

        return corrected_words

    def reload(self) -> None:
        """Reload all dictionaries."""
        self._dictionaries.clear()
        self._load_all_dictionaries()


# Singleton instance
def get_dictionary_service() -> DictionaryService:
    return DictionaryService.get_instance()
