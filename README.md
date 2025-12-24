# FORGE/LAB

**Atelier de viralité local** — Transformez vos VODs en clips verticaux viraux, prêts pour TikTok, Shorts et Reels.

![FORGE/LAB](docs/assets/banner.png)

## Fonctionnalités

- **Import local** : Glissez-déposez n'importe quelle VOD (mp4, mkv, mov)
- **Analyse virale** : Détection automatique des meilleurs moments avec scoring explicable
- **Layout intelligent** : Détection facecam, composition 9:16 automatique
- **Sous-titres premium** : Styles modernes, karaoke word-level, safe zones
- **Variants A/B/C** : Génération de multiples versions pour tester
- **Export complet** : Vidéo + cover + sous-titres + description + hashtags

## Prérequis

- **Node.js** 18+
- **pnpm** 8+
- **Python** 3.11+
- **FFmpeg** (avec support libass et optionnellement NVENC)

## Démarrage rapide

```bash
# Cloner et installer
git clone <repo> && cd forge-lab
pnpm install

# Configurer Python (une seule fois)
cd apps/forge-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
cd ../..

# Lancer en dev
pnpm dev
```

Ou utilisez le script de setup :

```powershell
.\scripts\setup.ps1
```

## Architecture

```
forge-lab/
├── apps/
│   ├── desktop/         # Electron + React (LAB UI)
│   └── forge-engine/    # Python FastAPI (FORGE Engine)
├── packages/
│   └── shared/          # Types partagés TS + Zod
├── docs/                # Documentation
└── scripts/             # Scripts utilitaires
```

## Commandes

| Commande | Description |
|----------|-------------|
| `pnpm dev` | Lance desktop + engine en dev |
| `pnpm build` | Build production |
| `pnpm test` | Exécute les tests |
| `pnpm lint` | Vérifie le code |

## Configuration

### Dossier Library

Par défaut, FORGE stocke les projets dans `~/FORGE_LIBRARY`. Personnalisable via :
- Variable d'environnement `FORGE_LIBRARY_PATH`
- Settings de l'application

### GPU (NVENC)

FORGE détecte automatiquement les GPU NVIDIA et utilise NVENC si disponible. Pour forcer le mode CPU :

```bash
FORGE_FORCE_CPU=1 pnpm dev
```

Vérifiez vos capacités FFmpeg :

```powershell
.\scripts\check-ffmpeg.ps1
```

## Demo

Pour tester avec une vidéo :

```powershell
.\scripts\demo.ps1 -VideoPath "C:\path\to\video.mp4" -ClipCount 3
```

## Documentation

- [Spécification fonctionnelle](docs/functional_spec.md)
- [Design Language](docs/design_language.md)
- [Architecture Pipeline](docs/pipeline.md)
- [Système de plugins](docs/plugin_system.md)
- [Troubleshooting](docs/troubleshooting.md)

## Licence

Propriétaire — Tous droits réservés.









