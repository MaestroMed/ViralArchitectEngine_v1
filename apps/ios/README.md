# FORGE LAB — iOS app

App native SwiftUI pour le workflow du matin :
1. **Review** des clips d'hier (générés automatiquement par le moteur).
2. **Download** sur la pellicule + légende auto-copiée dans le presse-papier.
3. **Ouverture TikTok** en 1 tap — colle, poste, terminé.

Pas de dépendance API TikTok, pas d'OAuth tier. Tout passe par la pellicule
et le Share Sheet du système.

## Pré-requis

- macOS + **Xcode 15+** (16 recommandé)
- `brew install xcodegen`
- Compte Apple Developer activé + `FORGE_APPLE_TEAM_ID` exporté
- iPhone (Air ou autre) en USB, déverrouillé, "Trust this Mac" accepté
- Le moteur FORGE/LAB lancé sur le PC qui sera sur **le même WiFi** que l'iPhone

## Configuration côté moteur

Avant de lancer l'app, prépare le moteur pour qu'il soit joignable :

```bash
cd apps/forge-engine

# Active le bind LAN + auth obligatoire dans .env :
echo 'FORGE_BIND_LAN=1' >> .env
echo 'FORGE_REQUIRE_AUTH=1' >> .env

# Crée la 1ère clé API (à coller dans l'app iOS au premier lancement)
python -m forge_engine.scripts.seed_api_key create "iPhone Air"
# → forge_XXXXXXXXXXX... (note-la, elle n'est affichée qu'une fois)

# Relance le moteur
pnpm dev
```

Note l'IP locale de ton PC (`ifconfig | grep "inet "` → `192.168.x.y`).

## Build + install sur l'iPhone

```bash
export FORGE_APPLE_TEAM_ID=ABC1234567        # ton ID dans developer.apple.com
./scripts/setup-ios.sh
```

Le script enchaîne :
1. `xcodegen` matérialise `ForgeLab.xcodeproj` à partir de `project.yml`
2. `xcodebuild archive` build + signe
3. `xcrun devicectl device install` push sur l'iPhone détecté

Première fois sur un nouveau profil dev iOS : *Réglages → Général → VPN et
gestion de l'appareil → faire confiance au profil développeur*.

## Premier lancement de l'app

1. Ouvre **FORGE LAB** sur l'iPhone.
2. Settings :
   - IP : `192.168.x.y` (ton PC)
   - Port : `8420`
   - Clé API : la valeur `forge_…` créée plus haut
   - **Tester** → "Connexion OK" → **Enregistrer**
3. Tu tombes sur la queue. Date par défaut = hier.
4. Tap sur un clip → preview → **Télécharger + ouvrir TikTok**.

## Architecture

```
apps/ios/
├── project.yml                    # XcodeGen
├── ForgeLab/
│   ├── ForgeLabApp.swift          # @main
│   ├── Info.plist
│   ├── ForgeLab.entitlements      # ATS local-networking
│   ├── Models/
│   │   ├── Clip.swift             # Codable miroir du backend
│   │   └── ApiError.swift         # Erreurs normalisées (401/429/etc.)
│   ├── Services/
│   │   ├── Settings.swift         # Persistance keychain (URL + clé API)
│   │   ├── ForgeAPI.swift         # Client URLSession async/await
│   │   ├── BundleDownloader.swift # ZIP → Photos + clipboard + TikTok
│   │   └── ZipReader.swift        # Lecteur ZIP_STORED (Foundation only)
│   ├── Theme/Theme.swift          # Couleurs + tokens UI
│   └── Views/
│       ├── RootView.swift         # Onboarding gate
│       ├── SettingsView.swift     # Config IP + clé + test connexion
│       ├── QueueView.swift        # Feed des clips du jour
│       ├── ClipDetailView.swift   # AVPlayer + actions
│       └── Components/ClipCard.swift
└── ForgeLabTests/
    ├── ForgeAPITests.swift        # URLProtocol mock (zéro réseau)
    └── ZipReaderTests.swift       # Archives en mémoire
```

## Endpoints consommés

Tous protégés par `X-API-Key` (sauf `/health` en clair, pour le test de
connexion).

| Méthode | Route                                | Vue              |
|--------:|--------------------------------------|------------------|
| GET     | `/health`                            | SettingsView     |
| GET     | `/v1/clips/by-date?date=YYYY-MM-DD`  | QueueView        |
| GET     | `/v1/clips/queue/summary`            | (badge à venir)  |
| GET     | `/v1/clips/{id}/cover`               | ClipCard         |
| GET     | `/clips/{id}/video` (avec Range)     | ClipDetailView   |
| GET     | `/v1/clips/{id}/bundle.zip`          | Download         |
| POST    | `/v1/clips/queue/{id}/approve`       | Detail + Card    |
| POST    | `/v1/clips/queue/{id}/reject`        | Detail           |
| POST    | `/v1/clips/batch-approve`            | QueueView (sél.) |

## Tests

```bash
cd apps/ios
xcodegen
xcodebuild test -project ForgeLab.xcodeproj -scheme ForgeLab -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

Couvre : décodage des payloads, envoi du header X-API-Key, 401/429/5xx,
sérialisation des batch requests, lecture ZIP, refus du DEFLATE.

## Choix de conception

- **Pas de SwiftData / CoreData** : tout vient de l'API, cache en mémoire
  uniquement. Quand on aura besoin de mode offline (queue locale d'actions),
  on l'ajoutera proprement avec un store.
- **Keychain pour la clé API** : iCloud-sync OFF, "this device only", read
  after first unlock. Une compromission de la sauvegarde iCloud ne révèle
  pas la clé.
- **Range requests pour le preview** : implémenté côté backend (voir
  `core/range_response.py`), AVPlayer scrub sans re-DL le clip entier.
- **ZIP_STORED côté backend** : `.mp4` déjà compressé → deflate sans intérêt.
  Évite une dépendance sur Compression.framework raw-deflate (peu pratique).
- **Pas de notifications APNS** au démarrage : APNS demande un certificat
  et un backend de push. À la place, badge local quand l'app voit des clips
  plus récents que sa dernière session.
