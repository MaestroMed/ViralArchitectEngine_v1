"""Channel Dictionary Service.

Manages per-channel dictionaries for improved transcription accuracy.
Learns frequently used terms from each streamer/channel and provides
them as context to Whisper for better recognition.

Features:
- Automatic learning from transcriptions
- Manual dictionary entries
- Channel-specific gaming terminology
- Named entity extraction (player names, game terms)
"""

from forge_engine.core.timeutils import utcnow
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ChannelDictionary:
    """Dictionary for a specific channel."""
    channel_id: str
    channel_name: str
    words: Counter = field(default_factory=Counter)  # word -> frequency
    custom_words: set[str] = field(default_factory=set)  # manually added words
    game_tags: set[str] = field(default_factory=set)  # detected game categories
    last_updated: str | None = None

    @property
    def top_words(self, limit: int = 100) -> list[str]:
        """Get most frequent words."""
        # Combine custom words with frequent words
        result = list(self.custom_words)
        for word, _ in self.words.most_common(limit):
            if word not in self.custom_words:
                result.append(word)
            if len(result) >= limit:
                break
        return result

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "words": dict(self.words.most_common(500)),  # Save top 500
            "custom_words": list(self.custom_words),
            "game_tags": list(self.game_tags),
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelDictionary":
        cd = cls(
            channel_id=data.get("channel_id", ""),
            channel_name=data.get("channel_name", ""),
            last_updated=data.get("last_updated"),
        )
        cd.words = Counter(data.get("words", {}))
        cd.custom_words = set(data.get("custom_words", []))
        cd.game_tags = set(data.get("game_tags", []))
        return cd


# Pre-built dictionaries for common content types
GAMING_DICTIONARY = {
    # French gaming slang
    "gg", "wp", "bg", "ez", "noob", "tryhard", "rush", "push", "focus",
    "call", "pick", "ban", "draft", "compo", "feed", "carry", "smurf",
    "boost", "rank", "ranked", "casual", "nolife", "grind",
    "farm", "xp", "level up", "stuff", "loot", "drop", "spawn", "respawn",
    # French reactions
    "incroyable", "dingue", "ouf", "chaud", "énorme", "stylé", "grave",
    "tranquille", "oklm", "frère", "frérot", "gars", "mec", "wallah",
    "sur ma vie", "je te jure", "genre", "en mode", "trop bien",
}

ESPORT_DICTIONARY = {
    # League of Legends
    "top", "jungle", "mid", "adc", "support", "gank", "dive", "roam",
    "flash", "tp", "téléportation", "peel", "engage", "drake", "dragon",
    "baron", "nashor", "herald", "héraut", "grubs", "inhib", "inhibiteur",
    "nexus", "ace", "pentakill", "quadra", "triple", "double", "first blood",
    "throw", "comeback", "snowball", "diff", "gap", "stomp", "outplay",
    # Karmine Corp & LFL/LEC
    "karmine", "kc", "kcorp", "kameto", "kamel", "prime", "kotei",
    "shaunz", "cabochard", "cinkrof", "saken", "caliste", "targamas",
    "rekkles", "upset", "hylissang", "adam", "113",
    "lec", "lfl", "lck", "lpl", "worlds", "msi",
    "g2", "fnatic", "vitality", "mad lions", "bds", "rogue",
    "ldlc", "solary", "gentle mates", "gameward",
    # Casters & personalities
    "chips", "noi", "rivenzi", "domingo", "zaboutine", "laure",
}

STREAMING_DICTIONARY = {
    # Twitch terms
    "stream", "live", "vod", "clip", "raid", "host", "sub", "abonné",
    "prime", "bits", "cheer", "emote", "chat", "viewer", "follow",
    "follower", "mod", "modérateur", "ban", "timeout", "mute",
    # French streaming
    "salut les kheys", "les amis", "la team", "bienvenue", "merci",
    "trop gentil", "on se retrouve", "à demain", "bonne nuit",
    "c'est parti", "let's go", "allez", "go go go",
}


class ChannelDictionaryService:
    """Service for managing channel-specific dictionaries.

    Stores dictionaries in LIBRARY_PATH/dictionaries/
    """

    _instance: Optional["ChannelDictionaryService"] = None

    def __init__(self):
        self.dictionaries_dir = settings.LIBRARY_PATH / "dictionaries"
        self.dictionaries_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, ChannelDictionary] = {}

        # Word extraction patterns
        self._word_pattern = re.compile(r'\b[a-zA-ZÀ-ÿ]{3,}\b')
        self._min_word_frequency = 3  # Minimum occurrences to include

    @classmethod
    def get_instance(cls) -> "ChannelDictionaryService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_dictionary_path(self, channel_id: str) -> Path:
        """Get path to dictionary file for channel."""
        # Sanitize channel_id for filename
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', channel_id)
        return self.dictionaries_dir / f"{safe_id}.json"

    async def get_dictionary(
        self,
        channel_id: str,
        channel_name: str | None = None
    ) -> ChannelDictionary:
        """Get or create dictionary for channel."""
        # Check cache first
        if channel_id in self._cache:
            return self._cache[channel_id]

        # Try loading from disk
        dict_path = self._get_dictionary_path(channel_id)
        if dict_path.exists():
            try:
                with open(dict_path, encoding='utf-8') as f:
                    data = json.load(f)
                dictionary = ChannelDictionary.from_dict(data)
                self._cache[channel_id] = dictionary
                logger.info("Loaded dictionary for channel %s: %d words", channel_id, len(dictionary.words))
                return dictionary
            except Exception as e:
                logger.warning("Failed to load dictionary for %s: %s", channel_id, e)

        # Create new dictionary
        dictionary = ChannelDictionary(
            channel_id=channel_id,
            channel_name=channel_name or channel_id
        )
        self._cache[channel_id] = dictionary
        return dictionary

    async def save_dictionary(self, dictionary: ChannelDictionary):
        """Save dictionary to disk."""
        from datetime import datetime

        dictionary.last_updated = utcnow().isoformat()
        dict_path = self._get_dictionary_path(dictionary.channel_id)

        try:
            with open(dict_path, 'w', encoding='utf-8') as f:
                json.dump(dictionary.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(
                "Saved dictionary for channel %s: %d words",
                dictionary.channel_id, len(dictionary.words)
            )
        except Exception as e:
            logger.error("Failed to save dictionary for %s: %s", dictionary.channel_id, e)

    def extract_words(self, text: str) -> list[str]:
        """Extract relevant words from text."""
        # Find all words
        words = self._word_pattern.findall(text.lower())

        # Filter common stop words
        stop_words = {
            "les", "des", "une", "que", "qui", "est", "pas", "pour", "dans",
            "sur", "avec", "mais", "donc", "car", "plus", "moins", "très",
            "bien", "tout", "tous", "elle", "lui", "nous", "vous", "ils",
            "sont", "ont", "fait", "faire", "être", "avoir", "aller",
            "the", "and", "that", "this", "with", "for", "are", "was",
            "were", "been", "have", "has", "had", "will", "would", "could",
        }

        return [w for w in words if w not in stop_words and len(w) >= 3]

    async def learn_from_transcription(
        self,
        channel_id: str,
        transcription_text: str,
        channel_name: str | None = None
    ):
        """Learn new words from a transcription."""
        dictionary = await self.get_dictionary(channel_id, channel_name)

        # Extract and count words
        words = self.extract_words(transcription_text)
        word_counts = Counter(words)

        # Update dictionary
        dictionary.words.update(word_counts)

        # Save periodically (after learning)
        await self.save_dictionary(dictionary)

        logger.info(
            "Learned %d words from transcription for channel %s (total: %d)",
            len(word_counts), channel_id, len(dictionary.words)
        )

    async def add_custom_words(
        self,
        channel_id: str,
        words: list[str],
        channel_name: str | None = None
    ):
        """Add custom words to channel dictionary."""
        dictionary = await self.get_dictionary(channel_id, channel_name)
        dictionary.custom_words.update(words)
        await self.save_dictionary(dictionary)
        logger.info("Added %d custom words to channel %s", len(words), channel_id)

    async def add_game_tag(
        self,
        channel_id: str,
        game_tag: str,
        channel_name: str | None = None
    ):
        """Add game tag to channel for specialized vocabulary."""
        dictionary = await self.get_dictionary(channel_id, channel_name)
        dictionary.game_tags.add(game_tag.lower())
        await self.save_dictionary(dictionary)
        logger.info("Added game tag '%s' to channel %s", game_tag, channel_id)

    async def get_prompt_words(
        self,
        channel_id: str,
        limit: int = 100,
        include_gaming: bool = True,
        include_esport: bool = True,
        include_streaming: bool = True
    ) -> list[str]:
        """Get words for Whisper initial prompt.

        Combines channel-specific words with category dictionaries.
        """
        words = []

        # Get channel dictionary
        dictionary = await self.get_dictionary(channel_id)

        # Add custom words first (highest priority)
        words.extend(dictionary.custom_words)

        # Add frequent channel words
        for word, freq in dictionary.words.most_common(limit):
            if word not in words and freq >= self._min_word_frequency:
                words.append(word)

        # Add category dictionaries based on settings/tags
        if include_gaming:
            words.extend([w for w in GAMING_DICTIONARY if w not in words])

        if include_esport or "esport" in dictionary.game_tags or "league of legends" in dictionary.game_tags:
            words.extend([w for w in ESPORT_DICTIONARY if w not in words])

        if include_streaming:
            words.extend([w for w in STREAMING_DICTIONARY if w not in words])

        # Limit to avoid overly long prompts
        return words[:limit]

    async def get_status(self) -> dict:
        """Get service status."""
        # Count dictionaries
        dict_files = list(self.dictionaries_dir.glob("*.json"))

        return {
            "dictionaries_count": len(dict_files),
            "cached_count": len(self._cache),
            "builtin_gaming_words": len(GAMING_DICTIONARY),
            "builtin_esport_words": len(ESPORT_DICTIONARY),
            "builtin_streaming_words": len(STREAMING_DICTIONARY),
        }
