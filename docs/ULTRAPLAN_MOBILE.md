# ULTRAPLAN — FORGE/LAB mobile « au propre »

> Doc-objectif maître (source de vérité long terme). Tient lieu de `/goal`.
> Exécuté en autonomie via `/loop` : à chaque itération, prendre la **prochaine
> tâche non cochée**, l'implémenter, la **vérifier** (render+frame / simulateur
> screenshot / tests), commit + push, cocher ici, notifier aux jalons.
>
> Vision : on a bâti un monstre (engine + app Electron desktop riche). Objectif :
> **transposer tout au propre sur mobile** — design **Liquid Glass (iOS 26)** +
> fonctionnalités de l'app Electron — ET **perfectionner les outputs clips**
> (cadrage facecam, fenêtres serrées, cold-open, titres).
>
> Contexte machine/clé : voir `RESUME.md` + mémoire de session. Engine local
> `.venv-full`, ffmpeg libass `~/FORGE_LIBRARY/bin/ffmpeg`. Branche `claude/review-codebase-gMN6t`.

## Principes
- **Toujours vérifier visuellement** : un clip = extraire des frames ; une vue
  iOS = builder + screenshot simulateur. Pas de "fait" sans preuve.
- **Petits incréments commités** ; CI verte ; tests à jour.
- **Jalons → PushNotification** à Mehdi (il pilote de loin).

---

## WS-A — Outputs clips parfaits (priorité immédiate, itératif sur la VOD d'Eto)
Projet de test : `1ab8b274-…` (VOD etostark__ v2796529250, cache analyse présent).

- [x] **A1. Cadrage facecam-en-haut** ✅ : layout deux-zones (cam d'Eto EN HAUT,
  contenu en bas) rendu correctement via `vstack`. Crash corrigé (source lue 2×
  + crops calculés sur dims de sortie au lieu de dims source). Ajout
  `PipelineConfig.facecam_ratio` (hauteur zone cam) câblé depuis `facecamRatio`.
  **Crops validés empiriquement** sur la vraie VOD (frames échantillonnées à
  420/1500/2600/3700/5900/6600s — la cam est toujours en bas à droite, tête
  centrée ~(0.83, 0.82)) : facecam x=0.70 y=0.71 w=0.255 h=0.29, content x=0.04
  w=0.63, ratio 0.42. Frame de sortie inspectée = visage d'Eto net en haut,
  contenu lisible en bas.
- [x] **A2. Robustesse layout** ✅ : (1) fallback center-crop propre si pas de
  layout_config (zone unique). (2) **Bug jump-cut corrigé** : avec ≥2 keep-ranges
  le concat lisait `[composed_v]` N× sans `split` ET ordonnait les pads
  all-video-puis-all-audio au lieu d'entrelacés par segment → crash rc=234
  ("media type mismatch"). Fix `split=N`/`asplit=N` + concat entrelacé. Chaîne
  complète (deux-zones + jump-cut + cold-open + sous-titres) testée rc=0.
  `test_pipeline_builder.py` (6 cas) verrouille les règles de pad.
- [x] **A3. Fenêtres serrées → durées variables** ✅ : remplacé "tout à 30s" par
  un **clustering** (`_cluster_segments`) : le segmenteur émet des fenêtres
  multi-échelle qui se chevauchent → on fusionne celles qui se chevauchent/sont
  proches (`merge_gap` 25s) en UN clip par moment (union, plafonné à
  `max_clip_seconds` 120s, centré sur le punch). Sur la VOD d'Eto : 6 fenêtres
  30s redondantes → ~9 clips distincts de 17s à 2min. `min_score` 65→60.
  `test_segment_clustering.py` (7 cas).
- [x] **A4. Cold-open réparé** ✅ : deux bugs corrigés — (1) la gate du hook
  utilisait `segment.duration` au lieu de `actual_duration` (durée effective
  clampée au max plateforme) → hook hors fenêtre → crash ; (2) le concat lisait
  `[composed_v]` 3× sans `split` (interdit) → "Error reinitializing filters".
  Fix : gate sur `actual_duration` + `split=3`/`asplit=3`. Vérifié : 12/12 clips,
  0 crash, cold-open (hook-first) appliqué sur les clips à hook fort.
- [x] **A5. Titres/légendes** ✅ (fallback) : Ollama absent → fallback FR amélioré
  (`_heuristic_caption`) = titre court entre guillemets = 1ère clause nettoyée +
  hashtags content-aware (#etostark #fail #esport #clutch…). Ex. `"Quand on fait
  des 180 dehors"`. + Garde anti-hallucination sur le texte source du titre.
  ➡️ Pour des accroches top-tier : installer Ollama (`brew install ollama` +
  `ollama pull llama3.2` + `FORGE_LLM_ENABLED=1`) — le LLM prend le relais auto.
- [x] **A7. Transcription propre ("bons modèles")** ✅ : cause des sous-titres
  "Sous-titres réalisés par Amara.org" = VAD désactivé en mode CPU pour les VODs
  > 1h → hallucinations sur les silences. **VAD toujours actif** (skip silences =
  + propre ET + rapide) + filtre `_is_hallucinated_segment` (boilerplate FR/EN +
  ghosts faible confiance) + `condition_on_previous_text=False`. Modèle **medium
  + int8 CPU** (1.43× temps réel vs 0.88× float32, sortie identique) via
  `WHISPER_CPU_COMPUTE_TYPE`. `test_transcription_hallucination.py` (16 cas).
- [x] **A6. Re-render batch propre** ✅ : 12 clips de la VOD d'Eto (la plus récente
  = v2796529250, confirmée via yt-dlp), cam-en-haut + captions medium propres +
  **durées 1-2min variées** (69/72/74/84/114s + 7×120s). Sélection greedy
  non-overlap (`_select_clips`) sur les fenêtres originales (reset depuis
  timeline.json) → vrai mix "parfois 1min parfois 2min" demandé par Mehdi.
  Vérifié : contact sheet 12/12 (cam-en-haut), span-check d'un clip 120s (cam
  reste en haut sur toute la durée). Queue propre (12 ClipQueue). Servis via
  tunnel cloudflared pour review off-LAN. Preview + sheet envoyés à Mehdi.
- [x] **A8. Sélection idempotente** ✅ : la sélection ne mute plus les lignes
  Segment canoniques (corruption à chaque run) — `run_export` accepte des
  overrides start/duration (segment détaché de la session avant tout commit).
  Lignes corrompues par les runs précédents réinitialisées depuis timeline.json.

## WS-B — App mobile : design Liquid Glass (iOS 26)
Cible : Xcode 26 / iOS 26, SwiftUI, APIs Liquid Glass (`glassEffect`, `GlassEffectContainer`,
`buttonStyle(.glass)`, etc. — **vérifier les API réelles via le SDK avant usage**).

- [x] **B1. Design system** ✅ : APIs Liquid Glass iOS 26 vérifiées (typecheck) ;
  `Theme/Glass.swift` = modifiers réutilisables (`forgeGlassCard`/`forgeGlassBar`/
  `forgeGlassAccent`) ; deployment target → iOS 26 ; `ClipCard` + barre de
  sélection + `GlassEffectContainer` sur la liste. Build OK + screenshot simulateur
  vérifié (cartes en verre). [B2 = appliquer aux autres écrans.]
- [x] **B2. Refonte des écrans existants** ✅ : QueueView (B1), ClipDetailView
  (carte metadata + boutons glass), SettingsView (fond sombre + rangées/boutons
  glass, route `--demo-screen settings` ajoutée). RootView ne fait que router.
  a11y identifiers + flux test/save conservés. Build + screenshots vérifiés.
- [x] **B3. Navigation** ✅ : NavigationStack + toolbars passent en Liquid Glass
  automatiquement sur iOS 26 (date-pill + menu vérifiés). App mono-surface → pas
  de TabView pour l'instant (viendra avec WS-C si on ajoute des sections).
- [x] **B4. Polish** ✅ : haptiques (`sensoryFeedback`) sur download/approve/reject,
  état vide en carte glass. Tests iOS verts (11 unit + 3 UI). [Reste possible :
  micro-animations de transition — à étoffer si besoin.]

## WS-C — App mobile : transposer les features de l'app Electron
Surface desktop (apps/desktop/src/pages) : Home, Project, ClipEditor, Analytics,
Templates, Settings, Surveillance, Admin, Onboarding. Adapter au mobile (pas tout
copier — repenser pour le tactile/petit écran).

> 📋 **Plan détaillé prêt à décider : [`docs/WS-C_MOBILE_PLAN.md`](WS-C_MOBILE_PLAN.md)**
> (survey multi-agents des 9 surfaces desktop + app iOS + contrats + endpoints,
> synthèse + critique adversariale). Propose une archi **4 onglets** (Pilot /
> Sources / Review / Stats), une table de transposition par surface (Port/Adapt/
> Skip + effort + priorité), les contrats/endpoints manquants, un ordre de build
> C1→C6, et **6 décisions produit à confirmer par Mehdi** avant de coder
> (déclencher des runs depuis le tel ? APNs + accès off-LAN ? Studio coupé en v1 ?
> publish YouTube-only ? quelles analytics ? mono-canal vs multi-projets ?).
> ⏳ **En attente des réponses de Mehdi (§5 du plan) avant implémentation.**

- [ ] **C1. Home/Dashboard** : résumé queue + stats + raccourci workflow matin.
- [ ] **C2. Project/VOD view** : liste des VODs/projets, statut pipeline, déclencher
  un traitement depuis le mobile.
- [ ] **C3. Clip editor mobile** : preview, ajuster in/out, choisir variante/layout,
  re-exporter.
- [ ] **C4. Analytics** : perfs des clips postés.
- [ ] **C5. Templates** : styles de sous-titres / presets d'export.
- [ ] **C6. Surveillance/monitoring** : état moteur (L'ŒIL), jobs en cours.
- [ ] **C7. Contrats** : tout passe par `@forge-lab/shared` (étendre les schémas
  mobiles pour les nouvelles surfaces) + endpoints backend manquants.

## WS-D — Accès & infra (pour piloter de loin)
- [ ] **D1. Accès distant durable** : remplacer le quick-tunnel cloudflared
  (URL éphémère) par un tunnel nommé stable ou Tailscale (action tel requise).
- [x] **D2. Auto-pipeline matinal réel** ✅ : `services/vod_detector.py`
  (détection VOD via **yt-dlp**, plus de Playwright) branché dans
  `_check_and_process` ; handle corrigé `etostark` → `etostark__`. Vérifié sur la
  vraie chaîne (liste les 4 dernières VODs) + `test_vod_detector.py`. `check_now()`
  détecte et traite désormais la dernière VOD automatiquement.

## État courant (2026-06-15)
- ✅ Engine durci, app iOS livrée + installée iPhone Air, contrats partagés, Alembic, e2e, ARIA.
- ✅ 1er batch réel : 12 clips karaoké 9:16 de la VOD d'Eto, servis (LAN + tunnel), 6 envoyés au tel.
- ✅ **WS-A TERMINÉ** : facecam-en-haut (A1), robustesse + jump-cut (A2), durées
  1-2min via sélection non-overlap (A3/A6), titres (A5), transcription medium+VAD
  (A7), sélection idempotente (A8). **12 clips livrés** de la dernière VOD d'Eto.
  WS-B (Liquid Glass) terminé. WS-D2 (auto-pipeline yt-dlp) fait.
- ✅ **WS-C** : plan décision-ready livré ([`WS-C_MOBILE_PLAN.md`](WS-C_MOBILE_PLAN.md)),
  en attente des 6 décisions produit de Mehdi avant implémentation.
- ▶️ **Accès distant actif** : engine UP + tunnel cloudflared
  `heavy-historical-acceptance-patients.trycloudflare.com` → review off-LAN
  depuis l'app iOS (clé API déjà sur l'iPhone Air).
- ⏭️ D1 (tunnel nommé stable / Tailscale) en attente action tel/compte.
