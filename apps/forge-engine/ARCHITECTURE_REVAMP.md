# Architecture FORGE 2.0 (Revamp)

## 1. Core System: Event-Driven & Persistent
The previous "in-memory" job system is replaced by a database-backed state machine.

### Data Model (SQLite)
- **Projects**: The container for VODs.
- **Jobs**: The source of truth.
  - `id`: UUID
  - `type`: 'ingest', 'transcribe', 'analyze', 'export'
  - `status`: 'pending', 'processing', 'completed', 'failed', 'cancelled'
  - `step`: Current sub-step (e.g., "ffmpeg_pass_1")
  - `progress`: 0-100 float
  - `payload`: JSON (input args)
  - `result`: JSON (output data)
  - `worker_id`: ID of the process handling it (for crash recovery)

### Process Isolation
- **API Server (Uvicorn)**: Handles HTTP requests and WebSockets. DOES NOT PROCESS VIDEO.
- **Task Runner (Background)**:
  - Polls DB for 'pending' jobs.
  - Locks job (status='processing').
  - Spawns isolated processes for heavy tasks (FFmpeg/Whisper).
  - Updates DB + Sends WebSocket event on progress.

## 2. Communication: WebSockets
- **Server**: `FastAPI` with `WebSocketEndpoint`.
- **Events**:
  - `JOB_CREATED`
  - `JOB_PROGRESS` {id, progress, step, speed}
  - `JOB_COMPLETED` {id, result}
  - `JOB_FAILED` {id, error}
- **Client**: React context `useWebSocket` that updates the global Zustand store.

## 3. Pipeline: "The Factory"

### Ingestion (Robust)
1. **Probe**: `ffprobe` JSON check.
2. **Hash**: Calculate fast hash (first 16MB) for duplicate detection.
3. **Proxy**: Generate 720p/30fps low-bitrate proxy immediately.
4. **Audio**: Extract WAV (16kHz mono) for Whisper.

### Analysis (Resume-capable)
- Broken down into atomic steps stored in DB.
- If step 2 fails, retry step 2, don't restart step 1.
- **Steps**:
  1. `transcription` (Whisper) -> saves `transcript.json`
  2. `diarization` (Pyannote/Custom) -> updates `transcript.json`
  3. `scene_detect` (PySceneDetect) -> saves `scenes.json`
  4. `scoring` (NLP + Audio) -> saves `virality.json`

## 4. Professional Editor (The Studio)
- **State**: Redux-like history (Undo/Redo).
- **Canvas**:
  - **Zone System**: Facecam Zone, Gameplay Zone.
  - **Auto-Tracking**: (Future) Center crop based on face detection.
- **Subtitles**:
  - Rendered as HTML/CSS overlays during edit.
  - Burned via FFmpeg filter complex during export.

## 5. Implementation Strategy
1. **Stop** current instability.
2. **Refactor** `JobManager` to read/write from DB, not RAM.
3. **Implement** WebSocket server.
4. **Connect** Frontend to WebSockets.
5. **Restart** Ingestion.




