# Reprise — FORGE/LAB (session locale)

> Dernière session : audit v1.5 complet + durcissement backend + app iOS native + automatisation matinale.
> Tout est sur `main` (et `claude/review-codebase-gMN6t`). Branche de dev : `claude/review-codebase-gMN6t`.

## Contexte / décisions actées
- **Pilote** : chaîne Twitch `etostark__` (configurée comme `etostark` dans `auto_pipeline.py`).
- **App iOS** : **native SwiftUI** (pas PWA). Workflow du matin : voir les clips d'hier → review → **download pellicule + légende copiée → ouvrir TikTok** (pas d'API TikTok, Share Sheet système).
- **Accès** : LAN (tel + PC même WiFi) + **clé API** (`X-API-Key`).
- **Compte Apple Developer** : déjà setup sur le Mac de l'utilisateur.

## ⚠️ Contrainte d'environnement (importante)
La session cloud précédente tournait dans un **sandbox Linux sans Xcode** → impossible d'y lancer le simulateur iOS ni compiler du Swift. Solution utilisée : **runner macOS GitHub Actions** (`.github/workflows/ios-preview.yml`) qui build + teste + screenshote + filme l'app. **En session locale sur le Mac, tu peux lancer le simulateur directement** (voir plus bas).

## État vérifié
- **Backend** : commande CI `test-backend` = **150 passed / 0 fail** ; `ruff check src/` = **clean**. Mes modules : 119 tests verts.
- **App iOS** : **compile** (Xcode 16 / iOS 17), **tous les tests passent** (prouvé sur CI run 27523903462) :
  - Unit : `ForgeAPITests` (6), `ZipReaderTests` (3) ✅
  - UI XCUITest : `testDeepLinkDetail`, `testQueueShowsDemoClips`, `testTapClipOpensDetail` ✅ (`** TEST SUCCEEDED **`)
- **Visuels produits** : 3 screenshots simulateur (`apps/ios/preview/screenshots/*.png`, commités) + `demo.mp4` (vidéo parcours queue→détail) + `TestResults.xcresult` dans l'artefact `ios-simulator-preview` du run.
- **Dernier fix poussé** : le workflow ios-preview se basait sur le code de sortie `xcodebuild` (non-zéro parasite au teardown CoreSimulator malgré succès) → corrigé pour se baser sur le marqueur `** TEST SUCCEEDED **`. **Le prochain run doit être vert.**

## Ce qui a été livré (commits sur main, du plus récent)
```
(workflow fix CI ios-preview — ce commit)
3dc1e37 test(ios): XCUITest UI flow + simulator video recording
0c65fb4 fix(deps): declare psutil (l'app ne bootait pas sans)
50603ba style: ruff-clean v1.5 (CI lint-backend était rouge)
1882f97 feat(automation): Phase 3 — Twitch webhook + export window + timezone
9b3e531 docs(ios): vrais screenshots simulateur
4d6cd8a fix(ios): catch shadowing @State error
c26fbdc ci(ios): build simulateur (macos-15 + UDID dynamique)
ceb8cd1 feat(ios): demo mode + mockup HTML + CI screenshots
3f147d3 feat(ios): app SwiftUI native complète + setup-ios.sh
2b1e3a7 feat(quality): scoring viralité v2 (TikTok 2026)
d0d9d13 feat(security): rate limiter + LLM escape + fix endpoints social
043a1c3 feat(api): endpoints mobiles + HTTP Range
049b987 chore: hygiène repo + checksums
870b97f feat(auth): clé API + bind LAN
69b91e4 fix: réparer CI cassé + re-appliquer sécurité P0 perdue au merge v1.5
```

## ▶️ PROCHAINE ACTION : voir/tester l'app dans le simulateur EN LOCAL (Mac)
```bash
cd apps/ios
brew install xcodegen        # une fois
xcodegen                     # génère ForgeLab.xcodeproj
open ForgeLab.xcodeproj      # → Cmd-R pour lancer dans le simulateur
# Lancer en mode démo (données etostark__, pas besoin du moteur) :
#   Product > Scheme > Edit Scheme > Run > Arguments > ajouter  --demo
# ou en ligne de commande :
xcodebuild test -project ForgeLab.xcodeproj -scheme ForgeLab \
  -destination 'platform=iOS Simulator,name=iPhone 16'
```
Le mode `--demo` (et `--demo-screen detail`) court-circuite l'onboarding + le réseau et peuple l'UI avec `DemoData.swift`.

## Installer sur l'iPhone Air physique
```bash
export FORGE_APPLE_TEAM_ID=<ton_team_id_10_chars>
./scripts/setup-ios.sh        # xcodegen → archive → devicectl install
```
Côté moteur (PC sur le même WiFi) :
```bash
cd apps/forge-engine
echo 'FORGE_BIND_LAN=1'      >> .env
echo 'FORGE_REQUIRE_AUTH=1'  >> .env
python -m forge_engine.scripts.seed_api_key create "iPhone Air"   # note la clé forge_…
pnpm dev
```
Puis dans l'app : IP du PC + port 8420 + la clé → Tester → Enregistrer.

## Architecture app iOS (`apps/ios/`)
- `ForgeLab/Models/` : `Clip` (Codable, miroir backend), `ApiError`
- `ForgeLab/Services/` : `Settings` (keychain), `ForgeAPI` (URLSession async), `BundleDownloader` (zip→Photos+presse-papier+TikTok), `ZipReader` (ZIP_STORED), `DemoData`
- `ForgeLab/Views/` : `RootView` (gate + demo), `SettingsView`, `QueueView`, `ClipDetailView`, `Components/ClipCard`
- `ForgeLabTests/` (unit) + `ForgeLabUITests/` (XCUITest)
- a11y identifiers posés : `clip-<id>`, `queue-list`, `download-button`

## Endpoints backend pour l'app (tous sous `X-API-Key` sauf `/health`)
`GET /v1/clips/by-date?date=YYYY-MM-DD` · `GET /v1/clips/queue/pending` · `GET /v1/clips/queue/summary` · `GET /v1/clips/{id}/cover` · `GET /v1/clips/{id}/bundle.zip` · `GET /clips/{id}/video` (Range/206) · `POST /v1/clips/queue/{id}/approve|reject` · `POST /v1/clips/batch-approve` · `POST /v1/webhooks/twitch` (HMAC, hors-auth)

## Reste au plan (non bloquant pour le workflow Photos)
1. ✅ **FAIT** — **Persistance chiffrée des credentials sociaux** : `core/crypto.py` (Fernet/MultiFernet, clé maître via `FORGE_SECRET_KEY` ou fichier `LIBRARY_PATH/.secret.key` mode 0600) + `services/credential_store.py` (blob `social_credentials.enc` chiffré, écriture atomique 0600) câblé dans `social_publish.py` (load au boot, persist après authenticate/disconnect). Scrubbing logs : `core/log_scrub.py` (filtre logging caviardant `access_token`/Bearer/Authorization/`X-API-Key`/`forge_…`) installé sur le handler root dans `main.py`. Tests : `test_crypto.py`, `test_credential_store.py`, `test_log_scrub.py`. Dép `cryptography>=42` ajoutée à requirements*/pyproject.
2. ✅ **FAIT** — **Câblage `@forge-lab/shared`** : contrat mobile typé dans `packages/shared/src/schemas/mobile.ts` (`ClipSchema` + enveloppes + `ClipMobileViewSchema` + types inférés). Fixture source-de-vérité unique `packages/shared/contract/mobile-clip.sample.json` **générée du vrai `ClipQueue.to_dict()`** (`scripts/gen_contract_fixture.py`). Tests de contrat **3 surfaces** : Python `test_contract_mobile.py` (clés backend), zod `contract/check-contract.mjs` (`pnpm --filter @forge-lab/shared test`, job CI `contract-shared`), Swift `MobileContractTests.swift` (décode le même fixture). ⚠️ Note de contrat : le backend émet des ISO **naïfs** (sans `Z`) → schéma zod tolérant (pas `.datetime()`).
3. ✅ **FAIT** — **Sweep ARIA desktop (web)** : ~38 correctifs (Sidebar nav+aria-current, ThemeToggle/AudioControls/toggles → aria-pressed/role=switch, Toaster→role=status/alert+aria-live, modals ShortcutsModal/JobDrawer/ExportModal/AIChat → role=dialog+aria-modal+aria-labelledby, lignes cliquables JobDrawer → role=button+clavier, Progress→progressbar, player SegmentPreview, forms SettingsPage/labels, OnboardingPage steps, SegmentFilterBar, TitleBar, web-review). Lint desktop : 0 erreur.
4. Migration Alembic (les nouveaux modèles passent par `create_all`).
5. Étoffer `test_pipeline_e2e.py` (rouge en sandbox par deps lourdes absentes ; le CI les ignore volontairement).

## Environnement local (Mac M5 Pro)
- Xcode 26.5 ; xcodegen, pnpm 8.12 (⚠️ le repo a un lockfile pnpm **v9** — utiliser pnpm 9 / corepack pour ne pas rétrograder `pnpm-lock.yaml`) ; venv backend : `apps/forge-engine/.venv` (Python 3.12 via brew, `requirements-ci.txt` + `cryptography` + `ruff`).
- Simulateur : `name=iPhone 17` (booté) ou `iPhone Air`. Lancer : `xcrun simctl launch booted com.maestromed.forgelab --demo [--demo-screen detail]`. Tests iOS : nettoyer `build/` avant (`-derivedDataPath build`, par UDID) sinon échec d'injection du bundle.
- Backend local : `cd apps/forge-engine && FORGE_LIBRARY_PATH=$(mktemp -d) .venv/bin/python -m pytest tests/ -m "not slow and not gpu and not e2e" --ignore=tests/test_pipeline_e2e.py --ignore=tests/test_export_real.py` → 182 passed.

## Vérif rapide en local
```bash
# Backend
cd apps/forge-engine && pip install -r requirements-ci.txt && \
  pytest tests/ -m "not slow and not gpu and not e2e" \
  --ignore=tests/test_pipeline_e2e.py --ignore=tests/test_export_real.py
ruff check src/
# Racine
pnpm install && pnpm lint && pnpm typecheck && pnpm test
```
