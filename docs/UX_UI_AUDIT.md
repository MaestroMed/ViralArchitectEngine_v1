# FORGE LAB — Prioritized Opportunity Map

*Head of Product Design · synthesis of 48 audited opportunities across 6 lenses
(IA · core flows/JTBD · visual craft · interaction/motion · copy/onboarding ·
differentiation), grounded in the shipping iOS code. Produced 2026-06-19.*

---

## 1. Verdict

The craft is already there: a coherent Liquid Glass system (`Theme`,
`forgeGlass*`, shared `SectionHeader`/`EmptyStateCard`/`PressableCardStyle`), a
real live-job spine (`ForgeSocket` streaming `JOB_UPDATE`/`PROJECT_UPDATE` with
reconnect/backoff), honest empty states, and per-outcome haptics in the export
flow. This is not a CRUD panel — it's 80% of a premium cockpit. **The one theme
to pursue: close the loop between "the engine finished" and "Mehdi reviews &
exports" — make the app *push* work to him and let him *clear a batch in
seconds*, instead of making him navigate to find work and tap through it one
clip at a time.** Two structural truths drive everything below: (a) the app has
zero push/deep-linking, so the "remote cockpit" promise is half-dead — Mehdi
must manually poll; and (b) the daily loop is friction-taxed by an Accueil tab
that duplicates Pilote's status and QueueView's count only to bounce the user to
tab 3, plus a one-at-a-time review/export flow on top of a `ForgeSocket` that
already knows everything in real time.

---

## 2. Top 5 high-leverage moves (do these next, in order)

### #1 — Push notification on "clips ready" + deep-link into review
**Opportunity:** When a VOD finishes analysis, fire a notification ("N clips
prêts") that deep-links straight to QueueView at today's date (and a clip-detail
variant).
**Why it matters (high):** This is *the* feature that makes "remote cockpit"
true. Today the engine can finish 8 clips and Mehdi has no idea until he opens
the app and manually swipes the date picker off "Hier." Everything else is
polish on a loop he doesn't know has new input.
**Effort:** Small-to-medium. The hard part — knowing when a job completes — is
**already solved**: `ForgeSocket` receives `JOB_UPDATE` with state transitions.
You need (a) `UNUserNotificationCenter` permission + a local notification on the
analyze→complete transition, and (b) URL routing. `RootView` already deep-links
by screen for `--demo`; generalize that into a real `onOpenURL` handler driving
`MainTabView.selectedTab` + a target date/clip.
**First step:** Add `forge-lab://clips?date=…` parsing in
`ForgeLabApp.onOpenURL` → set `initialTab` + a date binding on QueueView. Wire
one local notification off the `ForgeSocket` completion edge. Ship that thin
slice before touching remote APNs.

### #2 — Swipeable Triage Deck (full-screen review, swipe approve/reject/export)
**Opportunity:** A modal "Triage" mode that takes pending clips one full-screen
card at a time — autoplay 9:16 player, score, swipe-right approve / swipe-left
reject / tap export, advance to next.
**Why it matters (high):** The current loop is *tap card → push ClipDetailView →
decide → back → tap next*, repeated 5–15× every morning. The deck collapses that
to one gesture per clip. The single biggest daily-time win, and the kind of
motion-forward moment that makes the app feel premium rather than utilitarian.
**Effort:** Medium. Reuses `ClipDetailView`'s player/`ScoreBadge`/metadata and
the existing `api.approve`/`reject`. Gesture + card-stack choreography is new.
**First step:** Build a `TriageDeckView` over the *list* (not a tab) — entry via
a toolbar button on QueueView. Start with vertical paging + the existing detail
layout; layer swipe gestures and exit-animations second.

### #3 — One-tap batch export of today's approved clips
**Opportunity:** A "Télécharger les approuvés" CTA that queues all approved-
status clips, runs them through `BundleDownloader` sequentially with a progress
overlay, and aggregates captions.
**Why it matters (high):** `BundleDownloader` saves **one clip at a time**, and
`ClipDetailView` is the only export surface — exporting 8 clips = 8 round-trips.
Worse, each export copies its caption to the clipboard, so caption N overwrites
caption N-1. This turns ~10 minutes of tapping into one tap + a wait.
**Effort:** Small. Orchestrate existing `BundleDownloader.saveToPhotosAndShare`
in a loop; collect captions into a sheet instead of clobbering the pasteboard.
**First step:** Add a sequential batch method to `BundleDownloader` + a progress
overlay; render a "Légendes" sheet holding all captions with per-item copy.

### #4 — Collapse Accueil; make Clips the landing tab with a sticky status strip
**Opportunity:** Demote/remove Accueil. Land Mehdi directly in Clips (review)
with a thin sticky status strip ("Moteur connecté · v1.0.0 · ⚡2 en cours") and
keep the "Aujourd'hui" carousel at the top of the list. Reorder toward the
workflow: **Clips → Pilote → Sources → Stats**.
**Why it matters (high / structural):** `HomeView` literally re-renders Pilote's
engine footer and QueueView's pending count, then its hero CTA does
`selectedTab = 3` — an entire tab whose main job is to bounce you to another tab.
Removing the indirection puts the daily job at app-open. Paired with #1's
deep-link, a notification tap lands *in the queue*, not on a dashboard.
**Effort:** Medium. Mostly deletion + relocating the carousel and engine footer
into QueueView's header; the components already exist.
**First step:** Prototype QueueView with a pinned status strip + carousel header
behind a flag; validate it reads well before deleting `HomeView`. Preserve
first-run value/onboarding (Accueil currently carries the "welcome" weight).

### #5 — Score-Breakdown: "pourquoi c'est viral"
**Opportunity:** On ClipDetailView, a breakdown card decomposing the single
`viralScore` into components (hook, pacing, emotional peaks, audio clarity,
composition) as a mini bar/radial, with a one-line engine rationale.
**Why it matters (high differentiation):** The score *is* the reason Mehdi
reviews — yet it's an opaque "67". A breakdown turns the app from a remote
control into a coach: he learns what the algo rewards, trusts approvals faster,
and it's the feature he'd *show off*.
**Effort:** Medium, and **gated on backend**: needs a
`/v1/clips/{id}/score-breakdown` endpoint (the engine already scores per-segment,
so the data exists upstream). UI is a small glass card.
**First step:** Spec the breakdown contract with the engine side; stub the card
with the component schema so the iOS work and the endpoint land together.

---

## 3. Quick wins (small effort, real value — batch these)

- **Aggregate captions on batch export** (clipboard no longer overwrites) —
  folds into move #3.
- **Score badge as hero element:** larger `monospacedDigit`, dark scrim on
  covers, move to bottom-right on `HomePosterCard` (mirrors TikTok), faint glow
  at score ≥ 75. The badge is the decision signal; today it's tiny top-left.
- **Actionable error recovery:** replace passive "Moteur injoignable" (HomeView
  footer, PilotView empty state) with `[Réessayer] [Réglages]` inline actions +
  a "dernière tentative" timestamp. Today there's no retry affordance anywhere.
- **Unify status language:** canonical states (`EN ATTENTE / APPROUVÉ / PUBLIÉ /
  ÉCHEC`) with one pill size/grammar across ClipCard, ProjectCard, QueueView —
  currently project present-tense ("Analysé") collides with clip states
  ("Approuvé").
- **"Nouveau aujourd'hui" pill on QueueView** when the selected date ≠ today (the
  queue defaults to "Hier", so fresh clips are invisible without a manual date
  swipe). Cheap; large glanceability gain — a stopgap until #1 ships.
- **Contextual empty states + microcopy pass:** make each empty state point to
  the next action ("Importe une VOD dans Sources →"); tighten Settings copy to
  the confident voice of the hero.
- **"Vérifier toutes les chaînes" CTA** in Sources (today it's one tap per
  channel).
- **Health/predictive banner on Pilote** (disk < 20 GB, job > 90% of estimate,
  recent failure) — `HealthResponse`/`JobStats` are already fetched; just add
  thresholds.

---

## 4. Strategic bets (bigger reimaginings)

1. **Engine liveness, felt — not just shown.** Upgrade Pilote's static status
   header into a living indicator: pulsing dot when a job is active, "dernière
   vérif · 3 s", a shimmer sweep on the `ProjectCard` progress bar, a celebratory
   micro-animation on completion. *Upside:* the cockpit feels alive — the entire
   emotional pitch. *Risk:* over-animating a monitoring screen gets noisy; keep
   to 2–3 signature moves, respect Reduce Motion. Codify as reusable modifiers
   (`.pulseAccent`, `.shimmerProgress`, `.forgeLoader`) so it's a *system*.

2. **QR-pairing onboarding wizard.** Replace the raw Settings form (IP + port +
   `forge_…` key, which `RootView` dumps the user into on first run) with a
   Mac-generates-QR / phone-scans flow + "Enter manually" fallback. *Upside:*
   HomeKit-grade first impression; survives phone resets. *Risk:* needs a small
   Mac-side companion to emit the QR; without it, descope to a polished manual
   form with explicit labels and an inline "how to start the engine" sheet.

3. **First-run value + workflow teachback.** Since collapsing Accueil (#4)
   removes the "welcome" surface, give first-launch-after-setup a one-time
   contextual hero explaining the VOD→clips→export loop, then fade to the normal
   queue. *Upside:* newcomers understand *why* the queue is empty on day 1.

4. **Caption + transcript preview before export.** Show the exact clipboard
   string `fallbackCaption` will produce, editable, plus a transcript peek to
   catch Whisper hallucinations before a clip ships. *Upside:* near-zero effort
   (caption already computed), high trust.

5. **VOD pipeline timeline on Pilote.** Replace text job-stage rows with a
   horizontal `[Download]→[Transcribe]→[Analyze]→[Render]→[Complete]` timeline +
   wall-clock ETA, reusing the `ForgeSocket` stage/fraction data. *Upside:*
   opaque multi-hour jobs become legible momentum. *Risk:* larger build; do it
   after #1–#3, and only if ETA can be estimated honestly.

---

## 5. The bold bet

**Push + Triage Deck + Batch Export, shipped as one "Morning Review"
experience.** Individually these are moves #1–#3; together they're the product's
identity. The arc: *engine finishes → phone buzzes "8 clips prêts" → tap → land
in a full-screen deck → swipe through 8 in two minutes → one tap exports the
approved batch → done.* No tab-hunting, no date-picker archaeology, no per-clip
round-trips. This is exactly what a "premium remote cockpit for a technical owner
who's away from his desk" should feel like, and the foundation — a real-time
`ForgeSocket`, `batchApprove`, `BundleDownloader`, deep-link-capable `RootView`
routing — is already in the codebase. It's ambitious in *integration*, not in
invention, which is why it's the right bet: maximum differentiation, manageable
risk.

---

## 6. Explicitly de-scoped (don't build these now)

- **Merging Sources + Pilote into one "Ingestion" tab** — large effort;
  collapsing Accueil (#4) already reduces the bar to four. Don't churn IA twice.
- **Consolidating Stats into a modal/Settings panel** — net-neutral. After #4,
  Stats as the rightmost of four tabs is fine.
- **Custom inter-tab slide/parallax transitions** — fights the native iOS 26
  Liquid Glass tab bar for negligible benefit and real fragility. Spend the
  motion budget on engine-liveness and the export celebration instead.
- **Siri voice-to-batch-approve** — niche, large effort, and approving clips
  *without looking* contradicts a review tool whose value is visual judgment.
- **Swipe-to-trim / in-player scrubbing against segment boundaries** — real
  editing belongs on the Mac engine; the phone is export-not-publish *and*
  trim-not-edit.
- **Scheduling/staggered-post queue** and **hashtag-trending assistant** — both
  presuppose infrastructure that doesn't exist (a scheduler; external engagement
  data, currently 0/"à venir"). Building UI on absent data is how the "Vues — 0"
  deflation happens twice.
- **"Views" as a headline KPI** — keep it visibly deferred ("à venir") rather
  than a prominent 0; a zero in a hero slot reads as broken, not honest.

---

**Sequencing:** ship the quick-win bundle (§3) alongside move #1 in the first
cycle — they're independent and compounding. Moves #2–#4 form the "Morning
Review" arc (the bold bet). Move #5 + score-breakdown depend on backend
endpoints, so spec those contracts now so engine and app land together.

**Files this maps to:** `Views/MainTabView.swift` (tab order, deep-link
routing), `HomeView.swift` (collapse), `QueueView.swift` (landing, status strip,
new-today pill, deck entry), `ClipDetailView.swift` + `Services/BundleDownloader.swift`
(batch export, caption aggregation, score-breakdown card), `Services/ForgeSocket.swift`
(completion edge → notification, liveness), `Views/Components/{ClipCard,ProjectCard}.swift`
+ `UIComponents.swift` (score/pill/empty-state polish), `Views/RootView.swift` +
`ForgeLabApp` (`onOpenURL`), `Views/SettingsView.swift` (QR/onboarding).
