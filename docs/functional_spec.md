# FORGE/LAB - Spécification Fonctionnelle

## Vue d'ensemble

FORGE/LAB est un atelier de viralité local qui transforme des VODs (streams, podcasts, gameplay) en clips verticaux viraux optimisés pour TikTok, YouTube Shorts et Instagram Reels.

## Architecture

### FORGE Engine (Backend Python)
- FastAPI sur localhost:7860
- SQLite pour la persistance
- Job queue locale asynchrone
- FFmpeg pour le traitement vidéo
- faster-whisper pour la transcription

### LAB Desktop (Frontend Electron)
- React + Vite + TypeScript
- Tailwind CSS + Radix UI
- Framer Motion pour les animations
- Design "Westworld Lab"

## Flux Utilisateur

### 1. Import (Ingest)
1. L'utilisateur importe une VOD (mp4, mkv, mov)
2. Création d'un proxy 720p pour la prévisualisation
3. Extraction audio WAV 16kHz pour la transcription
4. Analyse des métadonnées (durée, résolution, pistes audio)

### 2. Analyse
1. Transcription avec faster-whisper (modèle configurable)
2. Détection de scènes via PySceneDetect
3. Analyse audio (énergie, peaks, silences)
4. Détection facecam avec OpenCV
5. Scoring viral des segments candidats

### 3. Forge (Édition)
1. Visualisation du "Viral DNA Map" (heatmap multicouche)
2. Exploration des segments classés par score
3. Configuration des layouts (facecam top/bottom)
4. Personnalisation des sous-titres
5. Génération de variants A/B/C

### 4. Export
1. Rendu final en 1080x1920 @ 30fps
2. Génération du cover image
3. Export des sous-titres (ASS, SRT, VTT)
4. Génération des métadonnées et post suggéré
5. Pack complet prêt à publier

## Scoring Viral

Chaque segment reçoit un score 0-100 basé sur :

| Critère | Points | Description |
|---------|--------|-------------|
| Hook Strength | 0-25 | Force de l'accroche initiale |
| Payoff | 0-20 | Qualité de la conclusion |
| Humour/Reaction | 0-15 | Présence d'éléments drôles/réactifs |
| Tension/Surprise | 0-15 | Éléments de tension ou surprise |
| Clarity/Autonomy | 0-15 | Compréhensibilité sans contexte |
| Rhythm | 0-10 | Rythme et pacing du segment |

## Formats de Sortie

### Vidéo
- Résolution : 1080x1920 (9:16)
- FPS : 30 ou 60
- Codec : H.264 (NVENC si disponible)
- Bitrate : Variable (CRF 23)

### Cover
- Format : JPEG
- Résolution : 1080x1920
- Overlay titre optionnel

### Sous-titres
- ASS : Avec styles et karaoke
- SRT : Format standard
- VTT : Pour le web

### Métadonnées
- JSON avec tous les détails du segment
- Scores, raisons, paramètres de rendu
- Checksums des fichiers

## API Endpoints

### Projets
- `POST /v1/projects` - Créer un projet
- `GET /v1/projects` - Lister les projets
- `GET /v1/projects/{id}` - Détails d'un projet
- `POST /v1/projects/{id}/ingest` - Lancer l'ingestion
- `POST /v1/projects/{id}/analyze` - Lancer l'analyse
- `GET /v1/projects/{id}/timeline` - Données du heatmap
- `GET /v1/projects/{id}/segments` - Lister les segments

### Jobs
- `GET /v1/jobs/{id}` - État d'un job
- `POST /v1/jobs/{id}/cancel` - Annuler un job

### Export
- `POST /v1/projects/{id}/export` - Exporter un segment
- `GET /v1/projects/{id}/artifacts` - Lister les exports

## Stockage Local

```
FORGE_LIBRARY/
├── forge.db              # Base SQLite
├── projects/
│   └── {project_id}/
│       ├── source/       # Fichier original
│       ├── proxy/        # Proxy 720p
│       ├── analysis/     # Transcript, timeline, etc.
│       ├── renders/      # Variants proxy
│       └── exports/      # Packs finaux
└── .temp/                # Fichiers temporaires
```

## Configuration

Variables d'environnement :
- `FORGE_LIBRARY_PATH` - Chemin du dossier library
- `FORGE_FORCE_CPU` - Forcer le mode CPU
- `FORGE_WHISPER_MODEL` - Modèle Whisper (default: large-v3)
- `FORGE_PORT` - Port du serveur (default: 7860)









