# FORGE/LAB - Architecture du Pipeline

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                         INGEST                              │
│  ┌─────────┐   ┌─────────────┐   ┌──────────────────────┐  │
│  │ Source  │ → │ FFprobe     │ → │ Create Proxy (720p)  │  │
│  │ Video   │   │ Metadata    │   │ Extract Audio (WAV)  │  │
│  └─────────┘   └─────────────┘   └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                         ANALYZE                             │
│  ┌───────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ Transcription │  │ Scene       │  │ Audio Analysis  │   │
│  │ (Whisper)     │  │ Detection   │  │ (Energy/Peaks)  │   │
│  └───────────────┘  └─────────────┘  └─────────────────┘   │
│          ↓                 ↓                 ↓              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Face/Layout Detection (OpenCV)           │ │
│  └───────────────────────────────────────────────────────┘ │
│                              ↓                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Virality Scoring + Segmentation          │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                          RENDER                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Composition Filter (Facecam + Content + Background)   ││
│  └─────────────────────────────────────────────────────────┘│
│                              ↓                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │     ASS Captions (Word-level karaoke + Styling)        ││
│  └─────────────────────────────────────────────────────────┘│
│                              ↓                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │        FFmpeg Encode (NVENC/libx264 + libass)          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                          EXPORT                             │
│  ┌─────────┐  ┌───────┐  ┌───────┐  ┌────────┐  ┌───────┐  │
│  │ MP4     │  │ Cover │  │ SRT   │  │ Post   │  │ JSON  │  │
│  │ Video   │  │ JPG   │  │ VTT   │  │ Text   │  │ Meta  │  │
│  └─────────┘  └───────┘  └───────┘  └────────┘  └───────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Étape 1 : Ingestion

### Probe Vidéo
```python
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4
```

Extrait :
- Durée, résolution, FPS
- Codec vidéo/audio
- Nombre de pistes audio

### Création Proxy
```bash
ffmpeg -i input.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -preset ultrafast -crf 28 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  proxy.mp4
```

### Extraction Audio
```bash
ffmpeg -i input.mp4 \
  -vn -ar 16000 -ac 1 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" \
  audio.wav
```

## Étape 2 : Analyse

### Transcription (faster-whisper)
```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    audio_path,
    word_timestamps=True,
    vad_filter=True
)
```

### Détection de Scènes
```python
from scenedetect import detect, ContentDetector

scene_list = detect(video_path, ContentDetector(threshold=27.0))
```

### Analyse Audio
```python
import librosa

y, sr = librosa.load(audio_path, sr=16000)
rms = librosa.feature.rms(y=y, hop_length=hop_length)
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
```

### Détection Facecam
```python
import cv2

face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5)
```

## Étape 3 : Scoring

### Critères de Score

```python
WEIGHTS = {
    "hook_strength": 25,     # Questions, exclamations, patterns d'accroche
    "payoff": 20,            # Conclusion forte, résolution
    "humour_reaction": 15,   # Marqueurs humour (mdr, lol, rires)
    "tension_surprise": 15,  # Variance audio, changements de scène
    "clarity_autonomy": 15,  # Compréhensible sans contexte
    "rhythm": 10,            # Pacing, mots/seconde, phrases courtes
}
```

### Déduplication
Les segments qui se chevauchent (IoU > 0.5) sont fusionnés, gardant le score le plus élevé.

## Étape 4 : Rendu

### Composition Verticale
```
┌───────────────────────┐
│       FACECAM         │ 40% hauteur
│   (crop + scale)      │
├───────────────────────┤
│                       │
│       CONTENT         │ 60% hauteur
│   (crop + scale)      │
│                       │
│  ─────────────────    │
│  SOUS-TITRES KARAOKE  │ Zone safe (75% du bas)
└───────────────────────┘
```

### Filtergraph FFmpeg
```
[0:v]crop=facecam_w:facecam_h:facecam_x:facecam_y,scale=1080:768[facecam];
[0:v]crop=content_w:content_h:content_x:content_y,scale=1080:1152[content];
[facecam][content]vstack=inputs=2[composed];
[composed]ass='captions.ass'[out]
```

### Encodage NVENC
```bash
ffmpeg -i input.mp4 \
  -vf "..." \
  -c:v h264_nvenc -preset p4 -cq 23 -b:v 0 \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  output.mp4
```

## Étape 5 : Export Pack

### Structure de sortie
```
exports/{segment_id}_{variant}/
├── clip_A_20241219_143022.mp4        # Vidéo finale
├── clip_A_20241219_143022_cover.jpg  # Cover image
├── clip_A_20241219_143022.ass        # Sous-titres ASS
├── clip_A_20241219_143022.srt        # Sous-titres SRT
├── clip_A_20241219_143022.vtt        # Sous-titres VTT
├── clip_A_20241219_143022_post.txt   # Texte pour publication
└── clip_A_20241219_143022_metadata.json
```

### Métadonnées JSON
```json
{
  "project_id": "...",
  "segment_id": "...",
  "variant": "A",
  "platform": "tiktok",
  "source_file": "stream_2024.mp4",
  "start_time": 1234.5,
  "end_time": 1264.5,
  "duration": 30.0,
  "score": {
    "total": 78,
    "hook_strength": 22,
    "reasons": ["Strong opening hook", "Good speech pacing"],
    "tags": ["humour", "surprise"]
  },
  "render_settings": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "use_nvenc": true
  },
  "exported_at": "2024-12-19T14:30:22Z"
}
```









