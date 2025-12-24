# FORGE/LAB - Système de Plugins

## Vue d'ensemble

FORGE supporte un système de plugins Python permettant d'étendre ses capacités :

- **Analyzers** : Nouveaux signaux d'analyse
- **Caption Styles** : Styles de sous-titres personnalisés
- **Scoring Models** : Modèles de scoring alternatifs
- **Exporters** : Formats d'export additionnels

## Structure d'un Plugin

```
my_forge_plugin/
├── __init__.py
├── setup.py
└── my_forge_plugin/
    ├── __init__.py
    ├── analyzers.py
    ├── caption_styles.py
    └── scoring.py
```

## Entry Points

Les plugins s'enregistrent via setuptools entry points :

```python
# setup.py
from setuptools import setup

setup(
    name='my-forge-plugin',
    version='1.0.0',
    packages=['my_forge_plugin'],
    entry_points={
        'forge.analyzers': [
            'chat_analyzer = my_forge_plugin.analyzers:ChatAnalyzer',
        ],
        'forge.caption_styles': [
            'neon_glow = my_forge_plugin.caption_styles:NeonGlowStyle',
        ],
        'forge.scoring_models': [
            'gaming_scorer = my_forge_plugin.scoring:GamingScorer',
        ],
    },
)
```

## Interfaces

### Analyzer Plugin

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseAnalyzer(ABC):
    """Base class for analyzer plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this analyzer."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        pass
    
    @abstractmethod
    async def analyze(
        self,
        project_path: str,
        audio_path: Optional[str],
        video_path: Optional[str],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run analysis and return results.
        
        Returns:
            Dict with 'timeline' (list of {time, value}) and 'metadata'
        """
        pass


# Example implementation
class ChatAnalyzer(BaseAnalyzer):
    """Analyze Twitch chat replay for engagement spikes."""
    
    @property
    def name(self) -> str:
        return "chat_analyzer"
    
    @property
    def display_name(self) -> str:
        return "Chat Spikes"
    
    async def analyze(self, project_path, audio_path, video_path, progress_callback=None):
        # Load chat log from project
        chat_path = os.path.join(project_path, "chat.json")
        
        if not os.path.exists(chat_path):
            return {"timeline": [], "metadata": {"error": "No chat log found"}}
        
        with open(chat_path) as f:
            messages = json.load(f)
        
        # Calculate message density per second
        timeline = []
        # ... processing logic ...
        
        return {
            "timeline": timeline,
            "metadata": {
                "total_messages": len(messages),
                "peak_rate": max_rate,
            }
        }
```

### Caption Style Plugin

```python
from abc import ABC, abstractmethod
from typing import Dict

class BaseCaptionStyle(ABC):
    """Base class for caption style plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        pass
    
    @abstractmethod
    def get_ass_style(self) -> Dict[str, Any]:
        """
        Return ASS style parameters.
        
        Returns dict with:
            font_family, font_size, primary_color, outline_color,
            outline_width, shadow_depth, alignment, margin_v, etc.
        """
        pass


# Example
class NeonGlowStyle(BaseCaptionStyle):
    @property
    def name(self) -> str:
        return "neon_glow"
    
    @property
    def display_name(self) -> str:
        return "Neon Glow"
    
    def get_ass_style(self) -> Dict[str, Any]:
        return {
            "font_family": "Arial Black",
            "font_size": 52,
            "primary_color": "&H00FF00FF",  # Magenta
            "outline_color": "&H0000FFFF",  # Cyan
            "outline_width": 4,
            "shadow_depth": 0,
            "bold": True,
            "alignment": 2,
            "margin_v": 200,
        }
```

### Scoring Model Plugin

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseScoringModel(ABC):
    """Base class for scoring model plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        pass
    
    @abstractmethod
    def score_segment(
        self,
        segment: Dict[str, Any],
        transcript_data: Optional[Dict] = None,
        audio_data: Optional[Dict] = None,
        custom_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Score a segment.
        
        Returns dict with:
            total (0-100), sub_scores (dict), reasons (list), tags (list)
        """
        pass


# Example
class GamingScorer(BaseScoringModel):
    @property
    def name(self) -> str:
        return "gaming_scorer"
    
    @property
    def display_name(self) -> str:
        return "Gaming Optimized"
    
    def score_segment(self, segment, transcript_data=None, audio_data=None, custom_data=None):
        text = segment.get("transcript", "").lower()
        score = 50  # Base
        reasons = []
        tags = []
        
        # Gaming-specific patterns
        if any(word in text for word in ["clutch", "win", "gg", "let's go"]):
            score += 20
            tags.append("clutch")
            reasons.append("Clutch moment detected")
        
        if any(word in text for word in ["fail", "rip", "dead"]):
            score += 15
            tags.append("fail")
            reasons.append("Fail moment")
        
        return {
            "total": min(score, 100),
            "sub_scores": {},
            "reasons": reasons,
            "tags": tags,
        }
```

## Découverte de Plugins

FORGE découvre automatiquement les plugins installés :

```python
import importlib.metadata

def discover_plugins():
    """Discover all installed FORGE plugins."""
    plugins = {
        "analyzers": [],
        "caption_styles": [],
        "scoring_models": [],
    }
    
    for ep in importlib.metadata.entry_points(group="forge.analyzers"):
        plugins["analyzers"].append({
            "name": ep.name,
            "loader": ep.load,
        })
    
    # Similar for other groups...
    
    return plugins
```

## Installation d'un Plugin

```bash
# Depuis PyPI
pip install forge-plugin-gaming

# Depuis source locale
cd my_forge_plugin
pip install -e .

# Redémarrer FORGE pour charger le plugin
```

## Création d'un Plugin

1. Créer la structure du package
2. Implémenter les classes héritant des bases
3. Configurer les entry points dans setup.py
4. Installer avec pip
5. Le plugin apparaît dans l'UI automatiquement

## Plugins Officiels (Roadmap)

- `forge-plugin-twitch-chat` : Analyse des logs chat Twitch
- `forge-plugin-youtube-comments` : Intégration commentaires YouTube
- `forge-plugin-whisperx` : Support word-level timestamps amélioré
- `forge-plugin-diarization` : Identification des speakers









