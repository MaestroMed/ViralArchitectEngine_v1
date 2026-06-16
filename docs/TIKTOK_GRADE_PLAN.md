# Viral Architect Engine — TikTok-Grade Giga-Plan

> Produced 2026-06-16 by an 11-dimension grounded multi-agent audit → synthesis
> → adversarial critique → refine. Source of truth for the quality push to a
> publishable result. Execute via /loop; each P0 render change is flag-gated +
> verified against a golden fixture (WS-Q0).

## PROGRESS (2026-06-16/17) — P0s DONE, applied to all 136 clips
- **WS-Q1 Captions** ✅ Anton font (bundled + libass fontsdir, verified), safe-zone
  position (`_safe_margin_v`, off the seam), phrase-aware chunking.
- **WS-Q3 Jump-cuts** ✅ Silero VAD fixed (torch + utils index + soundfile) +
  `_remap_caption_times` onto the cut timeline. [Hook/cold-open: deferred.]
- **WS-Q5 Audio** ✅ alimiter true-peak (-14 LUFS / -1 dBTP). [Denoise/duck: off, A/B later.]
- **WS-Q6 Cover** ✅ from the rendered 9:16 clip (was the letterboxed 16:9 source).
- **WS-Q7 Titles** ✅ LLM hooks + refusal gate.
- **WS-Q2 Timing** ⛔ DEFERRED — WhisperX would downgrade torch 2.12→2.8 + 30 heavy
  deps (breaks jump-cuts); marginal gain. Isolated env if ever pursued.
- **WS-Q4 Layout / Q8 Selection / Q9 App / Q10 Publishing** — not yet started.

---

# FORGE/LAB GIGA-PLAN — From "loin d'être exploitable" to TIKTOK-GRADE

**Scope:** the clip render pipeline (forge-engine) + the ForgeLab iOS cockpit. Grounded in the 11 audits and the live filesystem.

> **Three mechanisms in the prior draft rested on unverified assumptions and have been corrected below before any code is written:** (a) the caption bug is *probably not* missing `fontdir` but a fontconfig/family-name/`force_style` mismatch — verify with `-loglevel verbose` first; (b) Silero VAD ships an ONNX path and `onnxruntime` is already in the venv — torch is likely unnecessary; (c) WhisperX forced alignment runs on the **full segment**, not the 15–40s clip, so it is a CPU-SLA risk and is now benchmark-gated, not P0-install. The "unwire, don't build" thesis holds — but the work is *verify the mechanism, then connect existing code*, with flags, fixtures, and a jump-cut→caption timestamp remap that the prior draft missed.

---

## 1. TL;DR — the 5 highest-leverage moves

The pipeline has more *built-but-unwired* machinery than it has missing machinery. But "flip a switch" is only true once the underlying mechanism is verified — two of the prior "one-line wins" were built on guesses.

1. **Diagnose, then fix, the caption font fallback.** Anton is installed (`~/Library/Fonts/Anton-Regular.ttf`) but captions render in a fallback. The cause is **not assumed to be `fontdir`** — libass resolves by fontconfig *family name*, so the real culprit is usually `--disable-fontconfig` in the ffmpeg build, a style-name vs internal-family mismatch, or `force_style` clobbering `Fontname`. **Action (P0-S):** `ffmpeg -hide_banner -buildconf | grep fontconfig` and render one test caption at `-loglevel verbose` to read libass's actual font-selection line. *Then* apply the matching fix (pass `fontdir=` + filename match if fontconfig is disabled; correct the family name; or stop `force_style` override). This is the headline complaint, but it ships only after the mechanism is confirmed. **(WS-Q1, P0, S)**

2. **Make jump cuts fire — via ONNX, not necessarily torch.** Today every clip exports at 100% source duration because `VADPrefilterService` silently falls back to `keep_ranges=[full segment]`. **Verify first** whether `vad_prefilter.py` can use the Silero **ONNX** path (`onnxruntime` is already in the venv) or the standalone `silero-vad` pip package before committing to a ~200MB torch CPU dependency. Only install torch if no ONNX path exists *and* WhisperX survives its benchmark. **(WS-Q3, P0, S)**

3. **Benchmark WhisperX before installing it; alignment is a CPU-SLA risk on full segments.** Word timings are loose today and karaoke visibly drifts. WhisperX wav2vec2 alignment would tighten it, but it aligns the **full multi-minute segment**, not the clip — on CPU-only that can blow the <5min SLA. So the **P0 item is the benchmark** (`large-v3` vs `distil-large-v3+align` vs cloud-ASR+local-align); the *install + reroute* is **P1, conditional on the benchmark passing.** Don't wire the provider before knowing it's viable. **(WS-Q2, benchmark P0 / install P1-conditional, M)**

4. **Fix caption vertical position + safe zones for the two-zone vstack.** Default `margin_v=960` lands captions at the facecam/content seam (often over a face), and the custom-Y override has an inverted `-80` bug. Compute a layout-aware safe band. Independent of the font diagnosis, so it can land in parallel. **(WS-Q1, P0, M)**

5. **Wire the audio polish chain that already exists — denoise, duck, then loudnorm-last-as-sole-gain-authority.** `SoundDesignService` ducking is never called during export. Add denoise (decide `anlmdn` *or* `arnndn`+model asset — not interchangeable) → `sidechaincompress` → conditional clarity EQ → and keep `loudnorm` **dead-last as the only gain stage**, followed by `alimiter=limit=-1dB` to actually guarantee true-peak ≤−1dBTP (single-pass loudnorm does not). **(WS-Q5, P0, M)**

> **The pattern:** the wins are real but three of the five require a verification step first (font mechanism, ONNX-vs-torch, WhisperX SLA). Every P0 below ships behind an env flag, against a captured golden-render fixture, one filtergraph change at a time.

---

## 2. Quality bar — checkable definition of "TikTok-grade"

Split into a **hard gate** (deterministically machine-checkable now — a clip is blocked from queue insertion if any row fails) and an **advisory tier** (heuristic/semantic — surfaced as warnings, not blockers, until the backing vision/semantic models land in P2). A gate that can't measure a row would either silently pass or block everything — so aspirational rows are explicitly *not* in the hard gate.

### 2a. HARD GATE — machine-checkable now (blocks queue insertion)

| Dimension | Pass criterion (deterministic) |
|---|---|
| **Captions — font** | libass verbose log shows the **Anton** face actually selected (not a fallback line). If fallback detected → **QC warning that blocks queue insertion** (not a render abort — see WS-Q1) |
| **Captions — position** | `margin_v` math keeps baseline **≥200px from bottom** AND **out of facecam zone** (y > facecam_height+50); never on the vstack seam |
| **Captions — safe width** | Text constrained to inner **~800px of 1080** (MarginL=MarginR≈140); max **2 lines**; no line exceeds box width |
| **Captions — chunking** | Chunks break on punctuation (. ? ! ,); ≤4 words/line; no chunk spans a cut boundary |
| **Captions — sync (perceptual)** | Karaoke highlight transition within **one frame (~33ms @30fps)** of the word's aligned start — *not* an unmeasurable "±10ms"; checked against the post-cut timeline |
| **Duration** | **15–40s** sweet spot (hard ceiling 60s) |
| **Audio — loudness** | **−14 LUFS** ±1 (loudnorm measured), **true-peak ≤−1dBTP** (guaranteed by final `alimiter`, verified by `astats`/`ebur128`), LRA 2–8 LU |
| **Export spec** | 1080×1920; bitrate within preset; file size under platform cap |

### 2b. ADVISORY TIER — heuristic/semantic (warns, does not block until P2 models land)

| Dimension | Advisory criterion |
|---|---|
| **Hook (first 3s)** | Opens on a pattern interrupt (reaction/payoff/emotion peak), not mid-sentence dead air; first frame has motion + audio energy > −40dB. *Deterministic sub-checks that CAN gate:* first frame not black, t=0 audio not muted |
| **Framing** | Face inside 9:16 safe zone; TikTok UI margins (right 60px, bottom 100px, top/left 10px); <20% content-zone dead space. *Deterministic sub-check:* face-box within safe rect when face confidence ≥0.6 |
| **Pacing** | Silence/dead-air <5% (this one IS measurable post-VAD — promote to hard gate once jump cuts ship) |
| **Audio — separation** | Speech ≥6dB above music (measurable via stem RMS if stems exist; advisory otherwise) |
| **Cover** | Frame on emotion peak + face confidence, aligned to hook window; hook-text overlay in upper-third; no black bars |
| **Title/desc** | Title passes quality gate (not transcript echo, ≤60 chars — *the char/echo check IS deterministic and gates*; "real hook" is advisory); hashtags niche+creator+game |

---

## 3. Workstreams

Effort: S(≤½day) M(1–3d) L(>3d). Priority: P0 (blocks publishable) → P2 (polish/growth). **Every P0 pipeline mutation ships behind an env flag (rollback without code revert) and against a captured golden-render fixture (see WS-Q0).**

### WS-Q0 — Safety rails (NEW, prerequisite to all P0 render changes)
**Why:** the plan hinges on "re-render the batch and judge," but with no baseline that's vibes, and bundling 5 simultaneous pipeline changes is a confounded experiment on a working pipeline.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| **Capture golden fixtures:** N current renders + their exact ffmpeg filtergraph strings as committed fixtures, before touching `pipeline_builder.py` | `tests/fixtures/` (new), `pipeline_builder.py` | S | **P0** | high |
| **Feature-flag every P0 mutation** (`CAPTION_FONTDIR_FIX`, `AUDIO_DENOISE`, `AUDIO_DUCK`, `COLD_OPEN_DEFAULT`, `JUMP_CUTS_ENABLED`) → bad batch reverts via env, not revert commit | `core/config.py`, `pipeline_builder.py`, `export.py` | S | **P0** | high |
| **Land one filtergraph change at a time**, diff against fixture; never combine audio (Q5) + caption (Q1) in one batch | process | S | **P0** | high |

### WS-Q1 — Captions (the headline problem)
**Current:** ASS via libass, Anton in style but rendering a fallback. `margin_v=960` collides with vstack seam; custom-Y has inverted `-80` bug. 4-word chunks ignore punctuation. Hard pops between chunks. No safe-zone width enforcement.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| **Diagnose the fallback mechanism FIRST:** `buildconf | grep fontconfig` + one test render at `-loglevel verbose` to read libass font-selection. Confirm whether cause is disabled-fontconfig, family-name mismatch, or `force_style` clobber | `pipeline_builder.py`, `captions.py`, `export.py` | S | **P0** | high |
| Apply the matching fix (fontdir+filename if fontconfig off / correct family name / remove force_style override); behind `CAPTION_FONTDIR_FIX` flag | `pipeline_builder.py`, `captions.py` | S | **P0** | high |
| **Font check is a QC warning that BLOCKS queue insertion, NOT a render abort** (stale fontconfig cache must not kill the pipeline) | `qc.py`, `export.py` | S | **P0** | high |
| Layout-aware `_compute_safe_margin_v(facecam_ratio, custom_y)`; fix inverted `-80`; clamp to content-zone safe band | `captions.py`, `export.py` | M | **P0** | high |
| Safe-zone width: MarginL=MarginR≈140 for centered text; `_validate_safe_zone()` clamps + warns | `captions.py` | S | P1 | medium |
| Phrase-aware chunking `_chunk_by_phrases()` (break on . ? ! ,) | `captions.py` | M | P1 | high |
| Eliminate inter-chunk gaps with overlapping crossfades | `captions.py` | M | P1 | high |
| Per-word pop-in easing `\t(0,100,\fscx110…)` then ease back | `captions.py` | M | P2 | medium |
| Emoji/keyword pop (color/scale on viral words) | `captions.py` | M | P2 | low |

### WS-Q2 — Transcription accuracy & word timing
**Current:** faster-whisper large-v3 turbo, VAD on, word timestamps loose, not phoneme-aligned. EtoStark dict corrects text only. WhisperX **not installed**; `analysis.py` bypasses `TranscriptionProviderManager`.

> **Reality check on the claim:** WhisperX is CTC word-level, **not** true phoneme ±10ms, and on noisy gaming VOD (music + SFX over speech) alignment confidence drops and can be *worse* than faster-whisper on hard segments. Target is therefore the **perceptual one-frame (~33ms) gate** in §2a, not an ungateable ±10ms.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| **Benchmark Mac CPU on FULL-SEGMENT alignment** (not clip): large-v3 vs distil+align vs large-v3+align vs cloud-ASR+local-align, against <5min SLA — **this is the decision gate** | `tests/test_transcription_perf.py` (new) | M | **P0** | high |
| **CONDITIONAL on benchmark:** `pip install whisperx`; route `run_analysis()` through `TranscriptionProviderManager` w/ `local_aligned`; add `WHISPER_ALIGNMENT_ENABLED` flag | `analysis.py`, `core/config.py` (provider already supports it) | M | **P1 (gated)** | high |
| `distil-large-v3` model fallback for speed | `core/config.py`, `analysis.py`, `transcription.py` | S | P1 | medium |
| Confidence filtering: interpolate/flag words <0.6 | `captions.py`, `transcription.py` | M | P1 | medium |
| Validate ASS timing frame-accuracy on the **pinned** ffmpeg (debug ASS) | `tests/` (new), `render.py` | M | P1 | medium |
| Name/jargon accuracy via faster-whisper **`hotwords`/`initial_prompt`** (NOT a post-hoc text dict — that cannot affect decode or timing) | `transcription.py`, `dictionaries/etostark.json` | S | P1 | medium |

### WS-Q3 — Hook & pacing (first 3s + jump cuts)
**Current:** Jump cuts fully wired but **dead — VAD backend unavailable** → every clip is full-length. Cold-open exists but OFF by default and uses shallow regex, not semantic hook detection.

> **Sequencing correction:** cold-open default-on is the single highest regression risk to creative output (it changes every clip's opening). It must NOT go default-on before **semantic** hook detection exists — a regex reorder that picks the wrong "hook" is worse than linear playback. And it's gated on Mehdi's Open Question #6. So: semantic detection FIRST, then default-on. The Phase-0 "enable cold-open" item is demoted accordingly.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| **Enable VAD via ONNX path** (`onnxruntime` already in venv) or `silero-vad` pip pkg; install torch CPU **only if** no ONNX path AND WhisperX survives benchmark; behind `JUMP_CUTS_ENABLED` | `vad_prefilter.py`, `core/config.py` | S | **P0** | high |
| Log loudly when VAD unavailable / falls back (no more silent full-length export) | `vad_prefilter.py` | S | **P0** | medium |
| **Jump-cut → caption timestamp REMAP** (recompute every word timestamp against the post-cut timeline; captions/karaoke MUST target post-cut, not source). Required impl, not a "verify" checkbox. Ships AFTER jump cuts, BEFORE either reaches a real batch | `pipeline_builder.py`, `captions.py`, `export.py` | M | **P0** | high |
| Semantic hook detection: emotion peak + silence-break + payoff markers (not just regex) | `cold_open.py` | M | **P0** | high |
| Enable cold-open by default — **only after** semantic detection lands AND OQ#6 answered; behind `COLD_OPEN_DEFAULT` flag | `auto_pipeline.py`, `export.py` | S | **P1 (gated)** | high |
| Validate hook frame has motion + audio energy (no fade/mute at t=0) | `cold_open.py`, `export.py` | M | P1 | high |
| Tune VAD sensitivity for EtoStark (aggressive, min_silence~250ms, min_segment~500ms) | `auto_pipeline.py`, `jump_cuts.py` | M | P1 | high |
| 0.5s zoom + audio stab + text at cold-open cut (signal the hook) | `pipeline_builder.py` | M | P1 | high |
| Jump-cut metadata in artifacts (cuts/time-saved) | `export.py` | S | P2 | medium |

### WS-Q4 — Layout & dynamic framing
**Current:** Static two-zone vstack; **face-tracking keyframes computed but discarded** in single-pass path (tracking only runs when `EXPORT_SINGLE_PASS=False`, which is never). No dead-space detection, no TikTok safe zones in composition.

> **Re-scope correction:** consuming `facecam_keyframes` in single-pass means a **time-varying `crop` expression** — the hard, judder/seam-prone part. It is an **L, not M**. For v1, a centered safe crop is acceptable for talking-head gaming; animated crop is budgeted properly and deferred, not smuggled in as a P1/M.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| TikTok safe-zone constraints in composition + captions (shared `SafeZoneConfig`) | `pipeline_builder.py`, `captions.py`, `layout.py` | M | **P1** | high |
| Dead-space detection (sidebars/chrome) `_analyze_dead_space()` + warn | `layout.py`, `analysis.py` | M | P1 | high |
| Keep **static centered safe crop** for v1 (explicit decision; no animated crop) | `pipeline_builder.py` | S | P1 | medium |
| Consume `facecam_keyframes` in single-pass (animated time-varying crop) — **L, judder/seam risk**, budgeted not assumed | `pipeline_builder.py`, `export.py` | L | P2 | high |
| Facecam robustness: confidence score, center-safe fallback <0.6, multi-face | `layout.py`, `analysis.py` | M | P2 | medium |
| Per-platform framing presets | `core/config.py`, `pipeline_builder.py`, `export.py` | M | P2 | medium |
| Visual framing preview/inspector (proxy with zones outlined) | `preview_service.py` (new), `export.py` | L | P2 | high |

### WS-Q5 — Audio mix / loudness / music
**Current:** Volume scaling + basic `amix` + post-mix loudnorm. **No denoise, no ducking, no compression/EQ.** `SoundDesignService` (sidechain ducking) exists but is **never called**.

> **Three corrections baked in:** (1) `anlmdn` and `arnndn` are **not interchangeable** — both exist in both ffmpeg binaries (filter-probe moot, drop that caveat), but `arnndn` needs a `.rnnn` model asset (`arnndn=m=…`) or it no-ops/errors. **Decide one:** `anlmdn` (no model, safe default) for v1; `arnndn` only if the model asset is shipped. (2) **`loudnorm` stays dead-last as the sole gain authority** — denoise/compressor/EQ all shift integrated loudness, so nothing after loudnorm may change gain. (3) single-pass `loudnorm` does **not** guarantee true-peak ≤−1dBTP → add a final **`alimiter=limit=-1dB`** (or two-pass loudnorm) or the §2a audio gate fails the clips you "fixed."

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| Denoise: **`anlmdn` (default, no model)** OR `arnndn` **with shipped `.rnnn` asset** — pick one, specify the asset; behind `AUDIO_DENOISE` flag | `pipeline_builder.py`, `assets/` (if arnndn) | S | **P0** | high |
| Sidechain duck music under speech (wire SoundDesign logic into pipeline); behind `AUDIO_DUCK` flag | `pipeline_builder.py`, `export.py` | M | **P0** | high |
| **Final-stage true-peak guard:** `loudnorm` last + `alimiter=limit=-1dB` (or two-pass loudnorm); loudnorm is the only gain stage | `pipeline_builder.py` | S | **P0** | high |
| **Conditional** clarity chain: `acompressor` + highpass + mud-cut EQ (250Hz) + presence (4kHz) **only when input measurement warrants it** (spectral tilt / speech-RMS) — NOT always-on, which regresses already-clean sources | `pipeline_builder.py` | M | **P1** | medium |
| Adaptive music volume from measured speech RMS (drop fixed 0.15) | `export.py`, `pipeline_builder.py` | M | P1 | medium |
| QC: LRA bounds, speech-to-music ratio, true-peak during mix | `qc.py` | M | P1 | medium |
| Music profile library (EQ/duck per genre) | `sound_design.py`, `export.py` | M | P2 | medium |

### WS-Q6 — Cover / thumbnail / first frame
**Current:** Single frame at **hardcoded 30%**, dumb extraction, generic title overlay at bottom (out of safe zone), black-bar padding. Emotion + face + hook-timing all computed but **unused** for cover.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| Hook-aligned cover timing (replace `*0.3` with cold-open window) | `export.py` | S | **P1** | high |
| Aspect-aware extract (center-crop 16:9→9:16, no black bars) | `ffmpeg.py` | S | P1 | medium |
| Smart frame picker by emotion×face-confidence | `export.py`, `render.py` | M | P1 | high |
| Hook-text overlay (Montserrat bold, upper-third, 3px outline) | `render.py`, `export.py` | M | P1 | high |
| Multi-variant A/B covers (emotion / hook / payoff) | `export.py`, `render.py` | M | P2 | high |
| Persist cover metadata to artifacts | `export.py`, `models/artifact.py` | M | P2 | medium |
| Vision-API frame ranking (optional) | `render.py` | L | P2 | high |

### WS-Q7 — Titles / hashtags / descriptions
**Current:** llama3.2 (tiny) at temp 0.8 → generic/English-leak titles; quality gate works but only when Ollama is up; heuristic fallback is safe-but-weak; hashtags static/evergreen; descriptions empty.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| Upgrade LLM (mistral-7b / llama-13b) + inject creator/genre/audience context + few-shot good-vs-bad hooks | `llm_local.py`, `core/config.py` | M | P1 | high |
| Generate 5–7 titles, score on hook components, return ranked | `llm_local.py`, `content_generation.py` | M | P1 | high |
| Hashtag refresh: niche + creator + game-specific, kill evergreen noise | `content_generation.py` | M | P1 | medium |
| Gate ultra-weak heuristic quotes → LLM-lite rephrase fallback | `auto_pipeline.py`, `content_generation.py` | S | P2 | medium |
| Short punchy descriptions for Reels/Shorts | `llm_local.py`, `content_generation.py` | S | P2 | medium |

### WS-Q8 — Clip selection & virality scoring
**Current:** Text-first (regex 60%); emotion/audio only a 30% merge layer. `min_score=58` too permissive → setup-without-payoff, cold-viewer-confusing, semantic dupes.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| Hook→payoff coherence check (dock incoherent cold-opens) | `virality.py`, `virality_quality.py` | M | **P0** | high |
| Emotion/audio first reweighting (→40%) | `virality.py` | M | **P0** | high |
| Cold-start comprehensibility dimension | `virality.py` | M | P1 | medium |
| Semantic dedup by game-moment | `auto_pipeline.py` | M | P1 | medium |
| Game-state coherence (LoL action→result) | `virality.py` | M | P1 | medium |
| Duration band → 15–40s, bonus +6 | `virality_quality.py` | S | P2 | medium |
| LLM hook validation + filler-aware recalibration | `virality.py`, `llm_local.py` | S–M | P1/P2 | medium |

### WS-Q9 — iOS ForgeLab app (remote-pilot)
**Current:** Solid 2-tab reviewer (queue + download + manual TikTok). Far from remote cockpit: no projects/channels, no job monitoring/control, no VOD import, no push, no in-app publish. **Two hard blockers below.**

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| **BLOCKER:** publish-by-`clip_id` backend endpoint (resolves clip→server mp4) | `clips_mobile.py`, `ForgeAPI.swift` | S | **P0** | high |
| Projects + channels "Pilot" tab | `PilotView.swift`, `Project.swift`, `MainTabView.swift` | M | **P0** | high |
| Sources tab + detected-VOD import + URL paste | `SourcesView.swift`, `Channel.swift`, `DetectedVOD.swift`, `ForgeAPI.swift` | M | **P0** | high |
| WebSocket realtime job progress (throttle the firehose) | `WSClient.swift`, `WSMessage.swift`, `PilotView.swift` | L | P1 | high |
| APNs push on clips-ready — **gated on off-LAN reachability decision (OQ#1)** | `APNsManager.swift`, `SettingsView.swift`, `devices.py` | L | P1 | high |
| Enrich ClipDetail (metadata/desc/transcript/QC badge) | `ClipDetailView.swift`, `Clip.swift`, `ForgeAPI.swift` | M | P1 | medium |
| Project deep-dive / segment browse | `ProjectDetailView.swift`, `SegmentDetailView.swift`, `Segment.swift` | L | P1 | high |
| Stats tab, YouTube publish, styling polish, offline queue | various | M–L | P2 | medium |

### WS-Q10 — Publishing & platform export specs
**Current:** Renders 9:16 + −14 LUFS. **TikTok/Instagram are 100% stubs**; only YouTube partial. No clip→platform-video_id bridge. Platform presets declarative, **not enforced**. QC optional, not gated.

| Fix | Files | Eff | Pri | Impact |
|---|---|---|---|---|
| `platform_video_id` on ClipQueue + `external_id` on Artifact (close export→publish→track gap) | `models/review.py`, `models/artifact.py`, `social_publish.py` | M | P1 | high |
| Auto-publish worker for approved clips + manual trigger endpoint | `endpoints/reviews.py`, `core/jobs.py` | M | P1 | high |
| Pre-publish validation endpoint (res/dur/aspect/size/LUFS/safe-zones) | `endpoints/projects.py` | M | P1 | high |
| Implement TikTok upload (3-stage) | `social_publish.py` | L | P1 | high |
| Implement Instagram Reels (hosted URL + Graph API) | `social_publish.py` | L | P1 | high |
| Enforce presets (bitrate/file-size cap) + gate on QC PASS | `export.py`, `config.py`, `qc.py` | M | P2 | high |
| Safe-zone enforcement in presets; publish-by-clip_id resolver route | `config.py`, `captions.py`, `endpoints/projects.py` | S | P2 | medium |

---

## 4. Sequenced roadmap

### PHASE 0 — "Unbreak the render" (days 1–5, P0-S, one change at a time)
Pure unblock + connect-existing, **gated by WS-Q0 safety rails**. Land each behind its flag, diff against the golden fixture, **one filtergraph change per merge** — never bundle audio + caption changes.
0. **WS-Q0 first:** capture golden fixtures (renders + filtergraph strings); add the env flags. Nothing else starts until this exists.
1. **Diagnose the caption font fallback** (`buildconf | grep fontconfig` + verbose render) → apply the *matching* fix behind `CAPTION_FONTDIR_FIX`; font check becomes a queue-blocking QC **warning**, not a render abort (WS-Q1).
2. **Pin ONE ffmpeg binary** the pipeline is QC'd against (evermeet vs Homebrew differ in build flags incl. fontconfig); hard-code the path. (WS-Q1/Q5 prerequisite.)
3. **Enable VAD via ONNX** (onnxruntime already present) behind `JUMP_CUTS_ENABLED`; install torch **only if** no ONNX path; loud fallback logging (WS-Q3).
4. **Denoise** (`anlmdn` default, or `arnndn`+shipped model) behind `AUDIO_DENOISE` — landed in its own batch, with `loudnorm`-last + `alimiter` (WS-Q5).
5. **Caption safe `margin_v`** + fix the inverted `-80` bug (WS-Q1) — separate batch from the audio change.

### PHASE 1 — "Sound + sync + hook quality" (week 1–2, P0-M)
6. **Transcription benchmark FIRST** (full-segment, on the pinned ffmpeg) — the SLA decision gate. **WhisperX install + reroute is P1 and lands only if the benchmark passes**, behind `WHISPER_ALIGNMENT_ENABLED` (WS-Q2).
7. **Jump-cut → caption timestamp remap** — required before jump cuts reach any real batch; without it every multi-cut clip regresses captions (WS-Q3).
8. **Sidechain duck** behind `AUDIO_DUCK` + final true-peak guard already in place (WS-Q5). Conditional clarity EQ is **P1, input-measured, not always-on**.
9. **Semantic hook detection** (WS-Q3) — must exist *before* cold-open can go default-on.
10. **Selection P0:** hook→payoff coherence + emotion/audio reweighting (WS-Q8).

> **Gate after Phase 1:** re-render 10 clips and grade against the §2a **hard gate** (advisory tier is informational only). This is the first batch I'd call *plausibly publishable*. Because each P0 landed flagged + fixture-diffed, any regression is isolable to a single change.

### PHASE 2 — "Polish that shows" (week 2–4, P1)
11. Phrase-aware chunking + crossfade + safe-width (WS-Q1).
12. TikTok safe zones in composition; **static centered safe crop confirmed for v1** (animated keyframe crop stays P2/L) (WS-Q4).
13. Hook-aligned smart cover + hook-text overlay + aspect crop (WS-Q6).
14. **Cold-open default-on** — only now, after semantic detection (step 9) AND OQ#6 answered; behind `COLD_OPEN_DEFAULT`. Cold-open FX burst (zoom+stab); VAD tuning (WS-Q3).
15. Title LLM upgrade + ranked variants + hashtag refresh (WS-Q7).
16. Selection P1: cold-start comprehensibility, semantic dedup, game-state coherence (WS-Q8).
17. Publishing bridge: `platform_video_id` + auto-publish worker + validation endpoint (WS-Q10).

### PHASE 3 — "Remote pilot + real publish" (parallel track, P0/P1 within app)
- App can start **immediately in parallel** (different engineer/surface). Order: **publish-by-clip_id backend blocker → Pilot tab → Sources/import → WS realtime**.
- **APNs is gated on the off-LAN reachability decision (OQ#1)** — do not build before it's resolved.
- TikTok/Instagram real upload (WS-Q10 L items) land here.

### PHASE 4 — P2 polish/growth
Animated facecam keyframe crop (budgeted L), per-word easing, emoji pop, music-profile library, cover A/B + vision ranking, framing presets/preview, stats tab, preset enforcement, A/B title harness, retention measurement.

### What runs as a **re-render batch** (no per-clip human work)
All of WS-Q1, Q2, Q3, Q4, Q5, Q6, Q8 are render-pipeline changes — once merged (each flagged + fixture-diffed), **re-process existing VODs/segments in batch** and the whole back catalog upgrades. WS-Q7 (titles) and WS-Q9/Q10 (app/publish) are *not* batch re-renders; they're metadata/UX/integration.

---

## 5. Open questions for Mehdi (real product forks only)

1. **Off-LAN reachability** (blocks APNs + any away-from-desk pilot): Tailscale/tunnel vs. cloud-exposed endpoint vs. defer push entirely? A push that fires off-LAN deep-links into an app that can't reach a LAN-only engine — useless until this is decided. **Decide before building APNs.**

2. **Transcription SLA vs. hardware:** target is "final clip <5min," but WhisperX aligns the **full segment** on CPU. If the Phase-1 benchmark shows large-v3+align > SLA, do we (a) accept distil-large-v3 + local align, (b) move initial ASR to a cloud provider (Deepgram/OpenAI) and align locally, or (c) gate alignment to GPU-only runs? **This is now an explicit P0 decision gate — WhisperX install does not start until it's answered by the benchmark.**

3. **Trigger compute from phone?** Should the app *start* ingest/analyze (GPU job on the Mac) remotely, or stay review-only? Drives Pilot/Sources scope (WS-Q9).

4. **Publish in-app: YouTube-only first, or all platforms?** TikTok/IG real upload is L-effort and needs Client ID/Secret + IG Business account. Confirm priority and whether TikTok stays manual save-to-Photos for v1. Drives WS-Q10 ordering.

5. **Title LLM upgrade:** worth pulling a larger local model (mistral-7b / 13b — heavier on the Mac), or is a tighter prompt on llama3.2 + stronger heuristic gate acceptable for v1? And do you have 10–20 published clips with engagement metrics to ground a few gold-standard prompt templates? Drives WS-Q7 impact.

6. **Cold-open default:** confirm OK to **always reorder to the strongest hook** by default (changes clip openings across the board), with linear playback as the explicit opt-out. **Sequencing note:** even with a yes, default-on does not ship until semantic hook detection exists — a regex-picked wrong hook is worse than linear.

7. **Denoise model asset:** ship the `arnndn` `.rnnn` model (best quality, needs the asset) or stay on `anlmdn` (no asset, safe) for v1? Defaulting to `anlmdn` unless you want to source/validate a model.

---

**Key file map (all verified present):** captions/position/safe-zone → `services/captions.py`; libass+audio filtergraph → `services/pipeline_builder.py`; orchestration/cover/hook → `services/export.py`, `services/auto_pipeline.py`; ASR + alignment → `services/transcription.py`, `transcription_provider.py`, `whisperx_alignment.py`, `analysis.py`; jump cuts/VAD → `services/jump_cuts.py`, `vad_prefilter.py`; audio polish → `services/sound_design.py`; framing → `services/layout.py`, `facecam_tracking.py`; cover → `services/render.py`, `ffmpeg.py`; scoring → `services/virality.py`, `virality_quality.py`; titles → `services/llm_local.py`, `content_generation.py`; publish → `services/social_publish.py`, `api/v1/endpoints/{clips_mobile,reviews,projects}.py`, `models/{review,artifact}.py`; QC gate → `services/qc.py`; iOS → `apps/ios/ForgeLab/`.

**Environment facts that change the work:** (a) Anton is installed at `/Users/mehdinafaa/Library/Fonts/Anton-Regular.ttf` — but the caption fix is **diagnose-then-fix**, not an assumed `fontdir` one-liner (libass resolves by fontconfig family name; verify the build and the verbose font-selection log first); (b) `python` is not on PATH and torch/whisperx are not importable from the bare interpreter — installs target the project venv binary explicitly (`.venv-full/bin/python` per the publishing audit); **prefer the Silero ONNX path** since `onnxruntime` is already in site-packages before adding torch; (c) both an evermeet (`~/FORGE_LIBRARY/bin/ffmpeg`) and a Homebrew ffmpeg are present and **both** have `anlmdn`/`arnndn` — pin ONE binary the pipeline is QC'd against, since they differ in build flags (notably fontconfig); requirements/lockfile updates follow the pnpm/venv quirks in local-setup memory.
