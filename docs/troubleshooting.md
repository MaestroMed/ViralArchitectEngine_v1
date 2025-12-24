# FORGE/LAB - Troubleshooting

## Problèmes Fréquents

### Le moteur ne démarre pas

**Symptômes :**
- L'indicateur "Engine" reste rouge
- Erreur "Connection refused" dans la console

**Solutions :**

1. **Vérifier Python**
   ```powershell
   python --version
   # Doit être 3.11+
   ```

2. **Activer l'environnement virtuel**
   ```powershell
   cd apps/forge-engine
   .\.venv\Scripts\Activate.ps1
   ```

3. **Installer les dépendances**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Lancer manuellement**
   ```powershell
   python -m uvicorn forge_engine.main:app --host 127.0.0.1 --port 7860
   ```

### FFmpeg non trouvé

**Symptômes :**
- Erreur "FFmpeg not found"
- L'indicateur "FFmpeg" est rouge

**Solutions :**

1. **Vérifier l'installation**
   ```powershell
   ffmpeg -version
   ```

2. **Installer FFmpeg**
   ```powershell
   winget install FFmpeg
   # ou télécharger depuis https://ffmpeg.org/download.html
   ```

3. **Ajouter au PATH**
   - Panneau de configuration → Système → Variables d'environnement
   - Ajouter le dossier bin de FFmpeg au PATH

4. **Vérifier les capacités**
   ```powershell
   .\scripts\check-ffmpeg.ps1
   ```

### NVENC non disponible

**Symptômes :**
- L'encodage utilise libx264 (CPU lent)
- "NVENC not available" dans les logs

**Causes possibles :**
1. Pas de GPU NVIDIA
2. Drivers NVIDIA obsolètes
3. FFmpeg compilé sans support NVENC

**Solutions :**
1. Mettre à jour les drivers NVIDIA
2. Vérifier la présence de NVENC :
   ```powershell
   ffmpeg -encoders | findstr nvenc
   ```
3. Utiliser une build FFmpeg avec NVENC (gyan.dev)

### Whisper échoue ou est lent

**Symptômes :**
- Transcription très lente
- Erreur CUDA
- Out of memory

**Solutions :**

1. **Mémoire GPU insuffisante**
   - Passer à un modèle plus petit
   ```
   FORGE_WHISPER_MODEL=small
   ```

2. **Forcer le mode CPU**
   ```
   FORGE_FORCE_CPU=1
   ```

3. **Libérer la mémoire GPU**
   - Fermer autres applications GPU
   - Réduire la résolution du bureau

### L'analyse est bloquée

**Symptômes :**
- Progress bar figée
- Job en "running" indéfiniment

**Solutions :**

1. **Vérifier les logs**
   ```powershell
   # Les logs apparaissent dans le terminal du moteur
   ```

2. **Annuler et relancer**
   - Annuler le job depuis l'UI
   - Relancer l'analyse

3. **Redémarrer le moteur**
   - Arrêter pnpm dev
   - Relancer

### Erreur de rendu

**Symptômes :**
- Export échoue à X%
- Fichier corrompu

**Solutions :**

1. **Espace disque**
   ```powershell
   Get-PSDrive C | Select-Object Used,Free
   # Prévoir 2-3x la taille de la VOD
   ```

2. **Fichier source corrompu**
   - Tester avec VLC
   - Réencoder si nécessaire

3. **Filtres incompatibles**
   - Vérifier le log d'erreur FFmpeg
   - Simplifier le filtergraph

## Logs et Debug

### Activer les logs détaillés

```powershell
$env:FORGE_DEBUG = "1"
pnpm dev
```

### Localisation des logs

- **Engine** : stdout du terminal
- **Desktop** : DevTools (Ctrl+Shift+I)
- **FFmpeg** : stderr capturé dans les logs engine

### Base de données

```powershell
# Ouvrir la DB SQLite
sqlite3 "$env:USERPROFILE\FORGE_LIBRARY\forge.db"
.tables
SELECT * FROM projects;
```

### Reset complet

```powershell
# Supprimer la library (ATTENTION: perd tous les projets)
Remove-Item -Recurse -Force "$env:USERPROFILE\FORGE_LIBRARY"

# Réinstaller les dépendances
pnpm install
cd apps/forge-engine
pip install -r requirements.txt
```

## Support

Si le problème persiste :

1. Collecter les informations :
   - Version FORGE (visible dans Settings)
   - Version Windows
   - GPU (si applicable)
   - Logs complets

2. Créer un issue sur GitHub avec :
   - Description du problème
   - Étapes pour reproduire
   - Logs pertinents
   - Captures d'écran si utile









