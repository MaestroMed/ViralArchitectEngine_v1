# FORGE/LAB - Issues et TODO

## Connus / En cours

### Priorité Haute

- [ ] **Prévisualisation vidéo temps réel** : Le player vidéo n'est pas encore implémenté dans l'UI. Actuellement, seuls les métadonnées sont affichées.

- [ ] **WhisperX pour word-level précis** : faster-whisper fournit des timestamps word-level mais whisperX serait plus précis. À intégrer en option.

- [ ] **Electron build Windows** : Le build de production Electron nécessite une configuration supplémentaire pour inclure le moteur Python.

### Priorité Moyenne

- [ ] **Tests E2E** : Tests d'intégration complets du pipeline (ingest → analyze → export).

- [ ] **Gestion erreurs robuste** : Améliorer la gestion des erreurs et les messages utilisateur.

- [ ] **Tracking facecam amélioré** : Le tracking actuel utilise des snapshots, un tracking continu serait mieux.

- [ ] **OCR texte écran** : Détection du texte à l'écran (scoreboards, etc.) pas encore implémentée.

### Priorité Basse

- [ ] **Analytics loop** : Import des stats plateforme pour feedback.

- [ ] **Sound design** : Bibliothèque SFX et auto-duck musique.

- [ ] **Plugin marketplace** : Découverte et installation de plugins.

## Limitations Connues

1. **Mémoire GPU** : Le modèle Whisper large-v3 nécessite ~6GB VRAM. Utiliser un modèle plus petit si la mémoire est limitée.

2. **Durée VOD** : Les VODs très longues (>6h) peuvent être lentes à analyser. Envisager un traitement par chunks.

3. **Formats exotiques** : Certains codecs rares peuvent ne pas être supportés par FFmpeg. Convertir si nécessaire.

4. **Multi-speaker** : La diarization (identification des speakers) n'est pas encore implémentée.

## Contributions Bienvenues

- Amélioration des patterns de détection de hooks (français/anglais)
- Nouveaux styles de sous-titres
- Optimisations performance
- Tests supplémentaires
- Documentation multilingue









