# WS-C — FORGE/LAB Mobile Transposition Plan

> Decision-ready plan for transposing the Electron desktop features to the iOS
> app (SwiftUI, iOS 26 Liquid Glass). Produced 2026-06-16 by a multi-agent
> survey (9 desktop surfaces + iOS app + shared contracts + backend endpoints)
> + synthesis + adversarial critique. Grounded in the actual source — see the
> file references at the end. **Awaiting Mehdi's product decisions (§5) before
> building the write/compute/publish surfaces.**

---

## ✅ Delivered — C1 (Pilot, read-only) — 2026-06-17

The **decision-free** slice of C1 is built, tested, and on `claude/review-codebase-gMN6t`.
Everything below is **GET-only** (no compute triggers, no publish, no creds, no
destructive monitor routes) — so it ships without waiting on §5.

- **New "Pilote" tab** (3-tab shell: Accueil / Pilote / Clips): live engine-status
  header (health pill + version + active-jobs badge + capability chips:
  Whisper / sous-titres / GPU-CPU / espace libre) + the whole VOD **library** as
  Liquid-Glass project cards (thumbnail, status pill, platform, segments, avg
  score, duration, relative date).
- **ProjectDetailView** (read-only): hero thumbnail, full metadata grid, source
  link, and the project's recent jobs with progress.
- **Swift models** mirroring the engine: `Project`, `Job`, `Capabilities`,
  `ApiEnvelope<T>` / `Paginated<T>`, `HealthServices`; `ForgeAPI+Pilot`
  extension (`fetchProjects` / `fetchProject` / `fetchJobs` / `fetchJobStats` /
  `fetchCapabilities`, `projectThumbnailURL`, authed `imageData`).
- **Bug fixed in passing:** cover/thumbnail endpoints require the `X-API-Key`
  header which `AsyncImage` can't send → covers silently 401'd under LAN auth.
  New `RemoteImage` (authed loader + in-memory cache) powers project thumbnails
  **and repairs the existing clip covers**.
- **Verified:** clean build (0 warnings); 16 unit tests incl. a new
  `PilotContractTests` decoding **real** engine payloads
  (`apps/ios/ForgeLabTests/Fixtures/{projects,jobs,capabilities}.sample.json`);
  6 UI tests incl. Pilot + project-detail (clean simulator screenshots);
  passed a multi-agent adversarial review (contract / read-only / Swift).

**Still gated on §5 decisions:** C2 realtime WS spine, C3 Sources/APNs, C4
action-sheets (ingest/analyze triggers), publish, and any write path.

---

# WS-C — FORGE/LAB iOS Transposition Plan (decision-ready, revised)

**Frame:** This is a *remote-pilot cockpit*, not a desktop clone. Mehdi's phone is for **monitoring the engine, controlling ingest/VOD runs, and reviewing/approving clips** — heavy authoring (drag-crop, manual zone editing, multi-track mixing) stays on the Mac. Every call below biases toward **Adapt** over 1:1 Port, and toward **read + one-tap-act** over deep editing.

**What this revision corrected (verified against source):** Social in-app publish is a YouTube-only reality (TikTok/IG are backend stubs); `/social/publish` takes a server-side `video_path` the phone cannot supply (a real publish-by-`clip_id` GAP); the WS envelope was missing two message types; "manual connect" sends raw secrets (a security fork, not a default); the thumbnail "P0 gap" is smaller than stated; Whisper model picker, one-tap monitor actions, and the whole Studio tab were over-scoped; and `reject-archive` is likely a non-gap.

---

## 1. Recommended mobile information architecture

A **4-tab `TabView`** (Liquid Glass floating tab bar), each tab a `NavigationStack`. Studio is **dropped for v1** (see §5-Decision-3, now defaulted to cut): a *monitoring/approve* cockpit does not earn a full authoring tab, and re-export triggers a Mac-side GPU render. Light re-export folds into clip detail as a single action if ever needed.

| Tab | iOS name | Desktop pages it absorbs | Why |
|---|---|---|---|
| **1. Pilot** | `PilotView` (Home/Dashboard) | HomePage (project grid) + Monitor (L'ŒIL, mobile-safe slice) + Jobs drawer | The cockpit landing: live engine status, active jobs, project cards with progress. The "monitor the engine from the phone" surface — does not exist today. |
| **2. Sources** | `SourcesView` | SurveillancePage (channels + detected VODs) + URL import (from HomePage) | Where Mehdi *feeds the monster*: trigger a channel check, import a detected VOD, paste a URL. Pure remote-pilot. |
| **3. Review** | `QueueView` (existing) → enriched | clips_mobile queue + ProjectPage **Forge** (segment browse, read-only) + ClipDetail + artifacts + (YouTube) publish | The existing single surface, kept as the heart. Add per-project segment browsing, clip detail, artifacts, and YouTube-only publish. |
| **4. Stats** | `StatsView` | AnalyticsPage + per-clip performance | Glanceable KPIs + top clips for on-the-go review. Poll-based, battery-friendly. |

Settings stays a modal/sheet off Pilot's nav bar (not a tab — it's first-run config, not daily use). Social-account linking lives inside Settings.

**Justification:** 4 tabs is comfortably within the iOS sweet spot (Apple HIG, 380px bar). The split is by *intent*, not by desktop-page boundary — `ProjectPage`'s four desktop panels (Ingest/Analyze/Forge/Export) deliberately get *scattered*: Ingest/Analyze become one-tap actions on a Pilot project card, Forge-browse goes to Review, Export-variants (if kept) folds into Review's clip detail. A desktop's 4-panel wizard would be hostile on a phone.

---

## 2. Per-surface transposition table

| Desktop surface | Treatment | Target mobile screen | Key features to bring | Drop on mobile | Effort | Priority |
|---|---|---|---|---|---|---|
| **HomePage — project grid** | **Adapt** | Pilot tab (project cards, 1-col/2-col) | Card w/ thumb, status badge, score badge, duration, clip count, relative date; **live job progress overlay** (WS); search; tap→detail; one-tap primary action (Ingest/Analyze/Forge) | Hover overlays, context-menu, **local file import**, "open folder", Cmd-shortcuts | M | **P0** |
| **HomePage — URL import modal** | **Adapt** | Sheet from Sources tab | Paste URL → auto-fetch metadata (url-info), quality picker, auto-ingest/auto-analyze toggles, dictionary picker → import | Nothing major; enlarge tap targets | S | **P0** |
| **Monitor (L'ŒIL)** | **Adapt** (thin slice) | Pilot tab header + Jobs sheet | Engine connected/degraded pill, active-jobs list w/ progress (WS), stuck-jobs badge, **recover/pipeline-stop behind a confirm dialog**, pipeline start | Full logs viewer, service-by-service health grid, `reset-project`/`restart-project`/`cleanup-jobs` admin, auto-recovery config | M | **P1** |
| **ProjectPage — Ingest panel** | **Adapt** | Action sheet on Pilot card | Source metadata readout; toggles (proxy/extract-audio/normalize/auto-analyze); launch + progress ring | Audio-track selection (rare), advanced config | S | **P1** |
| **ProjectPage — Analyze panel** | **Adapt** | Action sheet on Pilot card | 4 step toggles, language, dictionary; **fixed `large-v3` default OR a 2-way fast/quality toggle** (no 7-way model enum); launch + progress | **Full `whisperModel` enum** (invites `tiny`-on-the-go → wrecks transcripts); inline dictionary editing (use a picker) | S | **P1** |
| **ProjectPage — Forge (segment browse/filter)** | **Adapt** | Review tab → Project subview | 1-col segment cards (score/duration/topic/thumb); filter by min-score + search + tags; sort; pagination; **smart suggestions** banner; segment detail card (score breakdown, hook, transcript, tags) | Timeline heatmap, multi-select-by-modifier, 2/3-col grid, drag-seek | M | **P1** |
| **ProjectPage — video preview + heatmap** | **Port** (player) / **Skip** (heatmap) | Segment detail | 9:16 / source player, play/pause, ±10s, mute, scrub, segment overlay | **Timeline heatmap** (too dense) → replace w/ score sparkline or count badge | S | **P1** |
| **ProjectPage — Batch export modal** | **Port** | Review tab action bar | Platform selector (2×2), "export all ≥70 / selected", progress (WS), cancel | — | S | **P1** |
| **ProjectPage — Export artifacts list** | **Adapt** | Review → Artifacts subview | Artifact cards (cover, size, date, **QC pass/warn/fail badge**), tap→play modal, download-to-Photos | "Open folder", QC raw JSON on hover→long-press | M | **P2** |
| **ClipEditorPage — whole surface** | **Drop for v1** | (none) — single "re-export with template X" action in Review clip detail *if* demanded | — (defer all authoring) | **Entire edit-lite tab**: source drag-crop, manual zone XYWH, multi-track mixer, music upload, jump-cut studio, template-save, re-export-variant (triggers Mac GPU render) | — | **Cut** |
| **TemplatesPage** | **Adapt** | Settings → Templates section (read/apply only) | Built-in 5 as fixtures; gallery (1-col), search, category chips, favorite, preview sheet; apply-on-export | File-picker import, download/export JSON, "create template", delete custom | S | **P2** |
| **SurveillancePage** | **Adapt** | Sources tab | Watched-channels list (avatar, platform, status, last-check); **manual check** (per-channel spinner); detected-VOD list (thumb, title, est. score); **import VOD** (→ job, WS); add-channel sheet; ignore VOD; delete channel | 3-col grid → 1-col | M | **P0/P1** |
| **AnalyticsPage** | **Adapt** | Stats tab | 4 overview KPI cards w/ trend; date range 7/30/90; top-clips list (rank, thumb, name, engagement); sort picker; refresh; empty state | **CSV export**, avg-watch-duration placeholder, hover states | M | **P2** |
| **SettingsPage** | **Adapt** (subset) | Settings sheet | Theme, ambient audio, export defaults (platform/subtitle/intro toggles), proxy quality, transcription provider pick + key entry (Keychain), **engine baseURL/key/test** (exists) | Library-folder mgmt, GPU/FFmpeg status grid, debug tools, experimental betas | S | **P1** |
| **OnboardingPage** | **Port** | First-run carousel | 5-step carousel, progress bar, dots, skip, swipe nav, UserDefaults persist | Nothing | S | **P2** |
| **Social (publish)** | **New — YouTube only** | Review → Publish action (YT) + Settings → Accounts | `/social/status` connected accounts; **YouTube Shorts publish** (only real backend publisher); publish-job status (WS); platform requirements check. **TikTok/IG stay save-to-Photos + manual post** (backend `_publish_tiktok`/`_publish_instagram` are stubs). Requires publish-by-`clip_id` GAP (below) | In-app TikTok/IG publish (months of app-review away); OAuth complexity → see Decision #4 security fork | M | **P2** |

---

## 3. Contracts & endpoints needed (P0/P1 surfaces)

### Shared schemas — what exists vs. must be added
`packages/shared/src/schemas/` already has the bulk. iOS today only consumes `mobile.ts`. To light up P0/P1, the iOS app needs **Swift Codable structs mirroring schemas that already exist in TS** (no new contract design, just Swift transposition + add to the CI contract check the way `Clip` is mirrored).

**Already defined in shared (TS) — only need Swift structs + fixture in `contract/` (verified):**
- `ProjectSchema`, `PaginatedResponseSchema`, `ListProjectsResponseSchema` → Pilot cards ✅
- `JobSchema`, `GetJobResponseSchema`, `IngestResponseSchema`, `AnalyzeResponseSchema` → job tracking ✅
- `SegmentSchema`, `ListSegmentsResponseSchema`, `GetSegmentResponseSchema` → Forge browse ✅
- `IngestOptionsSchema`, `AnalyzeOptionsSchema`, `ExportOptionsSchema` → action sheets ✅ (note: send a **fixed/2-way** `whisperModel`, do not surface the full enum)
- `TemplateSchema` → templates ✅
- `CapabilitiesResponseSchema`, `HealthResponseSchema` → Pilot status ✅
- `mobile.ts` clip contract → Review ✅ (already wired in Swift)

**Schemas that must be ADDED to shared (no zod today):**
- **WebSocket message envelope** — must cover the **full** `WSMessageType`: `JOB_UPDATE / PROJECT_UPDATE / EXPORT_PROGRESS / SEGMENT_DISCOVERED / ANALYSIS_PROGRESS / TRANSCRIPT_CHUNK / ERROR / SUBSCRIBED / PONG`. The earlier draft omitted `ANALYSIS_PROGRESS` and `TRANSCRIPT_CHUNK` (`websockets.py` lines 134/155) — omitting them means the Swift enum decoder **throws on live traffic** and the contract check fails. *(add — all nine)*
- **Channels** — `WatchedChannelSchema`, `DetectedVODSchema`, add-channel request, check response. *(add — Sources core)*
- **Analytics** — `DashboardOverviewSchema`, `TopClipSchema`. *(add — Stats)*
- **Social** — `SocialAccountSchema`, `PublishRequestSchema`, `PublishJobSchema`, platform-requirements. *(add — Publish, YouTube path)*
- **Monitor (mobile slice)** — trimmed `EngineStatusSchema` + `StuckJobSchema` (full monitor schema is too big/admin). *(add — Pilot status)*
- **Segment stats / suggestions / tags** — endpoints exist but aren't in shared zod. *(add — Forge browse)*

### Backend endpoints — exist vs. GAPS to build

**Exist and mobile-ready (P0/P1) — verified:**
- Projects: list/get/ingest/analyze/segments(+stats/tags/suggestions)/export-all/artifacts/thumbnail/import-url/url-info ✅
- Jobs: list/get/cancel/retry/stats ✅
- Channels: list/add/check/detected-vods/import/ignore ✅
- Clips mobile: by-date/batch-approve/bundle/cover/summary ✅; **reject already exists** as `POST /clips/queue/{clip_id}/reject` (single call — see GAPS note)
- Analytics: dashboard/overview/top-clips/trends ✅
- Social: status/accounts/connect/publish/publish-status/requirements ✅ **but `_publish_tiktok`/`_publish_instagram` are stubs; only `_publish_youtube` uploads** (`services/social_publish.py`)
- WebSocket: `/v1/ws`, `/v1/ws/project/{id}`, `/v1/ws/job/{id}` ✅
- Templates: full CRUD ✅
- Monitor: status/jobs/recover/pipeline start-stop ✅ (expose **only** the mobile-safe subset; see destructive-routes note)

**GAPS to build (from survey, ranked by pilot value):**
- **P0/P1 — Publish-by-`clip_id`** `POST /clips/{id}/publish` (or a server-side path-resolver). The existing `/social/publish` takes `PublishRequest.video_path: str` — a **server-side filesystem path** the service opens directly (`Path(request.video_path).exists()` / `open(video_path,"rb")`). A remote phone has no knowledge of the Mac's filesystem; it must publish by clip id and let the server resolve the rendered artifact. **This is a hard blocker for any phone publish, including YouTube.** *(net-new)*
- **P0/P1 — APNs push, scoped honestly.** No push infra exists anywhere in the backend (confirmed). This is **more than "cert + `/devices/register` + trigger"**: it needs an APNs auth key, per-event push-triggers wired into the job/clip/publish completion paths (multiple call sites), device-token storage + an Alembic migration, **and resolution of the off-LAN contradiction** (the engine runs on the Mac on LAN; the Mac can reach Apple's push gateway, but a push received off-LAN deep-links into an app that then **cannot load clips from a LAN-only engine**). See Decision #2 — the fork is *how to make the away-from-desk loop actually reachable* (e.g. tunnel/remote-access), not just "now vs. later." *(net-new, larger than first scoped)*
- **P1 — Thumbnail size param (re-scoped, smaller).** Not a new list endpoint. `by-date` already returns the clip list, and a generic `thumbnails.py` router already serves project/segment thumbnails. The real gap is **adding a `?w=`/`size=small` query to the existing `GET /clips/{clip_id}/cover`** for server-side downscale on cellular. *(small enhancement, not P0 new-build)*
- **P1 — Caption preview without full export** `GET /segments/{id}/caption-preview?style=` — only relevant if any re-export survives in Review's clip-detail; otherwise defer with Studio. *(net-new)*
- **P2 — Quick social auth deep-link** `POST /social/quick-auth` — replaces raw-credential entry; see security fork in Decision #4. *(net-new)*
- **P2 — Export history per segment** `GET /segments/{id}/export-history` — "what's already published". *(net-new)*
- **P2 — Offline review sync** (queue offline decisions → reconcile) — only if Mehdi reviews without connectivity; defer behind a decision. *(net-new)*
- **~~reject-archive atomic endpoint~~ — likely NOT a gap.** `reviews.py` already exposes `POST /clips/queue/{clip_id}/reject` (single call). The "PATCH + DELETE = two round-trips race" was a misreading. **Verify whether `reject` already archives** before building anything; do not build `reject-archive` on the stated premise.

---

## 4. Proposed build order (milestones C1…C6)

Studio (formerly C5) is **dropped**; sequencing is reflowed so **pilot value lands by C3** (monitor engine + control sources + review), then deep-dive and analytics.

- **C1 — Shell + Pilot read-only.** 4-tab `TabView`; migrate existing Queue/Detail/Settings into tabs; build `PilotView` project cards (list/get) + engine status pill (capabilities/health). Swift structs for Project/Job/Capabilities. *Outcome: Mehdi sees the whole library + engine health on the phone.*
- **C2 — Realtime spine.** WS client (`/v1/ws`) with reconnect; shared + Swift WS contract covering **all nine** message types; wire live job-progress overlays onto Pilot cards + a Jobs sheet; one-tap cancel; recover/pipeline-stop **behind a confirm dialog**. **Explicitly drop or coalesce `TRANSCRIPT_CHUNK`/`ANALYSIS_PROGRESS`** (firehose during a job → battery/decode cost): decode-and-discard or throttle to a progress %, never render the stream. *Outcome: live monster monitoring without battery burn.*
- **C3 — Sources control + (read/approve) loop.** Channels list + manual check + detected-VOD import (→ job, WS); URL-import sheet; **APNs registration + push on clips-ready/job-failed** — *contingent on resolving the off-LAN reachability fork (Decision #2)*. Publish is **not** in C3 (demoted to P2, YouTube-only, blocked on the publish-by-`clip_id` GAP). *Outcome: feed VODs, get pushed when clips are ready, review/approve — from the phone.*
- **C4 — Project deep-dive in Review.** Segment browse/filter/suggestions + segment detail (player, score breakdown, transcript) + batch export ≥70 + ingest/analyze action sheets (**fixed/2-way Whisper default, no model enum**). Add segment + stats schemas. *Outcome: act on a specific project, not just the daily queue.*
- **C5 — Stats.** Overview KPIs + date range + top-clips + per-clip performance. *Outcome: glanceable performance.*
- **C6 — Polish + YouTube publish (if greenlit).** Onboarding carousel; Settings subset (theme/audio/export defaults/provider keys); artifacts QC list; thumbnail `?w=` enhancement; and — **only if Decision #4 picks in-app + the publish-by-`clip_id` GAP is built** — YouTube Shorts publish in Review with publish-job WS status. *Outcome: polish, plus optional YT auto-publish.*

---

## 5. Decisions needed from Mehdi (real forks only)

1. **Trigger heavy runs from the phone — yes/no?** C3 lets Mehdi *import a VOD* and *kick ingest/analyze* remotely (a long GPU job on the Mac). Confirm he wants the phone to **start** compute, not just review output. If no → Sources becomes read-only "queue for later," much smaller.

2. **APNs — and the off-LAN reachability it depends on.** Push is the biggest lever for the away-from-desk loop, but the real fork is **reachability, not timing**: a push that fires while Mehdi is off-LAN deep-links into an app that can't reach a LAN-only engine to load the clip. Decide the access model (e.g. Tailscale/reverse-tunnel/exposed endpoint) *before* committing APNs to C3; without it, push notifies but can't deliver the clip. Build cost is also larger than first scoped (auth key, multi-site triggers, token storage + migration).

3. **Studio — now defaulted to CUT for v1.** Reversing the earlier "keep it, but minimal." A monitoring/approve cockpit doesn't earn an authoring tab, and every re-export fires a Mac-side GPU render. **Default: 4-tab app, no Studio, no C5-authoring.** Fold a single "re-export with template X" action into Review's clip detail *only if* Mehdi says he needs on-the-go variants. Confirm the cut (or re-instate the tab and its full cost).

4. **Publish: YouTube-only in-app + a security fork on connect.** Two coupled choices:
   - (a) **In-app publish is YouTube-only today.** TikTok/IG `_publish_*` are backend stubs (TikTok returns "requires app review"); in-app TikTok/IG is months away. Pick: build **YouTube Shorts in-app publish** (needs the publish-by-`clip_id` GAP) vs. keep **all platforms save-to-Photos + manual post** for v1.
   - (b) **Account connect is a security decision, not a default.** `/social/accounts/connect` takes `credentials: dict[str,str]` — raw secrets in a JSON body over the LAN API. Choose: **manual-creds-now** (accept sending platform tokens/passwords from the phone) vs. **wait for OAuth/`quick-auth` deep-link**. This is a hardening call, not a "ship manual first" given.

5. **Which analytics actually matter on mobile?** Confirm the glance set = {views, engagement, top-clips}. Per-variant A/B comparison would need a `variants/performance` GAP and bumps Stats effort.

6. **Single-channel pilot vs. multi-project switching everywhere?** Today the app is one queue. Confirm the phone should surface *all* projects/channels (assumed yes, drives Pilot+Sources) vs. staying scoped to one active channel for simplicity.

---

**Relevant grounding files (absolute):**
- iOS app: `/Users/mehdinafaa/ViralArchitectEngine_v1/apps/ios/ForgeLab/` (`Models/Clip.swift`, `Services/ForgeAPI.swift`)
- Shared contracts: `/Users/mehdinafaa/ViralArchitectEngine_v1/packages/shared/src/schemas/{index.ts,api.ts,mobile.ts}` (`whisperModel` enum in `index.ts`/`AnalyzeOptions`); `/Users/mehdinafaa/ViralArchitectEngine_v1/packages/shared/contract/check-contract.mjs`
- Backend endpoints: `/Users/mehdinafaa/ViralArchitectEngine_v1/apps/forge-engine/src/forge_engine/api/v1/endpoints/` — `social.py` (raw `credentials` dict, `PublishRequest.video_path`), `websockets.py` (`ANALYSIS_PROGRESS`/`TRANSCRIPT_CHUNK` at lines 134/155), `monitor.py` (destructive `reset-project`/`restart-project`/`cleanup-jobs`/`pipeline/stop`), `reviews.py` (existing `/clips/queue/{id}/reject`), `clips_mobile.py` (`/cover` has no size param), `router.py` (router prefixes)
- Publish service: `/Users/mehdinafaa/ViralArchitectEngine_v1/apps/forge-engine/src/forge_engine/services/social_publish.py` (stub `_publish_tiktok`/`_publish_instagram`, real `_publish_youtube`, `video_path` usage)
