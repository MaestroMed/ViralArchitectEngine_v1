# FORGE Engine

Moteur de traitement vidéo pour FORGE/LAB.

## Installation

```bash
# Créer l'environnement virtuel
python -m venv .venv

# Activer (Windows)
.\.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

## Développement

```bash
# Lancer le serveur en mode dev
python -m uvicorn forge_engine.main:app --reload --host 127.0.0.1 --port 7860

# Ou via pnpm depuis la racine
pnpm --filter @forge-lab/engine dev
```

## Tests

```bash
# Exécuter les tests
pytest tests -v

# Avec couverture
pytest tests -v --cov=src/forge_engine
```

## API

Documentation disponible sur `http://localhost:7860/docs` en mode dev.

## Structure

```
src/forge_engine/
├── api/              # Endpoints FastAPI
├── core/             # Config, DB, Jobs
├── models/           # Modèles SQLAlchemy
└── services/         # Services métier
    ├── ffmpeg.py     # Traitement vidéo
    ├── transcription.py  # Whisper
    ├── virality.py   # Scoring
    ├── layout.py     # Détection facecam
    ├── captions.py   # Sous-titres ASS
    ├── render.py     # Rendu final
    └── export.py     # Export packs
```









