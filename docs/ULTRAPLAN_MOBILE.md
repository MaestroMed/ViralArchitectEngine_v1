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

- [~] **A1. Cadrage facecam-en-haut** — EN COURS (itératif, voir note).
  - ✅ Plomberie : `_run_single_pass_export` retombe sur `segment.facecam_rect`
    quand pas de `layout_config` (gaté `stream_facecam`), donc l'export sait
    composer le deux-zones aussi en auto-pipeline.
  - ⚠️ **Détection trop grossière** : `layout.detect_layout` rend UN layout GLOBAL
    pour toute la VOD (ici `podcast_irl` + facecam 120×120 unique). Sur une VOD
    multi-scènes (on-cam + contenu produit plein écran), il faut une détection
    **par segment/scène** + gating de confiance (deux-zones seulement si vraie
    webcam détectée dans CE segment, sinon center-crop). Cette VOD "WAITING ROOM"
    est surtout du contenu produit → peu/pas de webcam Eto à isoler.
  - ➡️ TODO : détection facecam par-segment + valider sur une VOD où Eto est
    bien on-cam (input Mehdi).
- [ ] **A2. Robustesse layout** : fallback propre si pas de facecam stable
  (talk_fullscreen / center-crop) ; ne jamais crasher l'export.
- [x] **A3. Fenêtres serrées** ✅ : `_auto_export_top_clips` resserre chaque clip à
  `max_clip_seconds` (30s) centré sur le punch (`cold_open_start_time`, lead-in 5s)
  avant export. Vérifié : 12 clips à 30s, karaoké OK. Config `etostark` mise à jour.
- [x] **A4. Cold-open réparé** ✅ : deux bugs corrigés — (1) la gate du hook
  utilisait `segment.duration` au lieu de `actual_duration` (durée effective
  clampée au max plateforme) → hook hors fenêtre → crash ; (2) le concat lisait
  `[composed_v]` 3× sans `split` (interdit) → "Error reinitializing filters".
  Fix : gate sur `actual_duration` + `split=3`/`asplit=3`. Vérifié : 12/12 clips,
  0 crash, cold-open (hook-first) appliqué sur les clips à hook fort.
- [ ] **A5. Titres/légendes LLM** : lancer Ollama (ou fallback heuristique amélioré)
  → vraies accroches FR au lieu du transcript brut.
- [ ] **A6. Re-render batch propre** de la VOD d'Eto avec A1-A5 → notifier Mehdi.

## WS-B — App mobile : design Liquid Glass (iOS 26)
Cible : Xcode 26 / iOS 26, SwiftUI, APIs Liquid Glass (`glassEffect`, `GlassEffectContainer`,
`buttonStyle(.glass)`, etc. — **vérifier les API réelles via le SDK avant usage**).

- [ ] **B1. Design system** : tokens (couleurs/typo/espacements) + composants
  Glass réutilisables (cartes, barres, boutons) ; thème sombre par défaut.
- [ ] **B2. Refonte des écrans existants** (RootView, QueueView, ClipDetailView,
  SettingsView) en Liquid Glass — garder les a11y identifiers + le workflow matin.
- [ ] **B3. Navigation** : TabView/NavigationStack Liquid Glass cohérente.
- [ ] **B4. Polish** : animations, haptiques, transitions, états vides/chargement.

## WS-C — App mobile : transposer les features de l'app Electron
Surface desktop (apps/desktop/src/pages) : Home, Project, ClipEditor, Analytics,
Templates, Settings, Surveillance, Admin, Onboarding. Adapter au mobile (pas tout
copier — repenser pour le tactile/petit écran).

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
- [ ] **D2. Auto-pipeline matinal réel** : brancher la détection VOD etostark__
  (le scraper Playwright cible `etostark` au lieu de `etostark__`, et Playwright
  n'est pas installé) → fiabiliser la découverte + traitement automatique.

## État courant (2026-06-15)
- ✅ Engine durci, app iOS livrée + installée iPhone Air, contrats partagés, Alembic, e2e, ARIA.
- ✅ 1er batch réel : 12 clips karaoké 9:16 de la VOD d'Eto, servis (LAN + tunnel), 6 envoyés au tel.
- ✅ 8 bugs prod corrigés en conditions réelles (voir RESUME.md).
- ▶️ **Prochaine tâche : A1 (cadrage facecam-en-haut).**
