import AVKit
import SwiftUI

/// MVP in-app clip editor (CapCut-style "restyle + re-render"): pick a dynamic
/// caption style and re-render the clip in place. No trim / transcript-edit yet.
///
/// Flow: choose a preset → tap "Re-render" → engine queues an EXPORT job → we
/// track that jobId over the live WS feed → on completion we swap the AVPlayer
/// item for the refreshed (cache-busted) video URL and show a success state.
///
/// Demo-safe: in `--demo` the carousel renders from a hardcoded preset list, the
/// player shows a gradient placeholder, and the CTA is inert. No network, no
/// continuous animation (gated on `!AppLaunch.isDemo`) so XCUITest stays idle.
struct ClipEditorView: View {
    let api: ForgeAPI
    let clip: Clip
    let demo: Bool

    @StateObject private var model: EditorModel

    init(api: ForgeAPI, clip: Clip, demo: Bool = false) {
        self.api = api
        self.clip = clip
        self.demo = demo
        _model = StateObject(wrappedValue: EditorModel(api: api, clip: clip, demo: demo))
    }

    var body: some View {
        ScrollView {
            GlassEffectContainer(spacing: 16) {
                VStack(alignment: .leading, spacing: 18) {
                    playerCard
                    presetSection
                    colourSection
                    trimSection
                    captionSection
                    rerenderSection
                    if let job = model.trackedJob {
                        progressCard(job)
                    }
                    if model.succeeded {
                        successBanner
                    }
                }
            }
            .padding()
            .animation(.easeInOut(duration: 0.25), value: model.succeeded)
            .animation(.easeInOut(duration: 0.25), value: model.trackedJob != nil)
        }
        .background(Theme.background)
        .navigationTitle("Éditer")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await model.loadPresets()
            await model.loadCaptions()
        }
        .onDisappear { model.teardown() }
        .sensoryFeedback(.success, trigger: model.successTick)
        .sensoryFeedback(.error, trigger: model.errorTick)
    }

    // MARK: - Preview

    @ViewBuilder
    private var playerCard: some View {
        if demo || model.player == nil {
            RoundedRectangle(cornerRadius: Theme.Radius.lg)
                .fill(LinearGradient(
                    colors: [Color(red: 0.09, green: 0.20, blue: 0.31), Color.black],
                    startPoint: .top, endPoint: .bottom,
                ))
                .aspectRatio(9 / 16, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .overlay(Image(systemName: "play.circle.fill").font(.system(size: 56)).foregroundStyle(.white.opacity(0.9)))
                .accessibilityElement()
                .accessibilityLabel("Aperçu vidéo indisponible")
        } else if let player = model.player {
            VideoPlayer(player: player)
                .id(model.playerGeneration)   // force a fresh view when we swap the item
                .aspectRatio(9 / 16, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .background(Color.black)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.lg))
                .onAppear { player.play() }
                .onDisappear { player.pause() }
                .accessibilityLabel("Lecteur vidéo du clip")
        }
    }

    // MARK: - Preset carousel

    private var presetSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Style de sous-titres", systemImage: "textformat")
                .font(.headline).foregroundStyle(Theme.textPrimary)
            Text("Choisis un look dynamique, puis relance le rendu.")
                .font(.caption).foregroundStyle(Theme.textSecondary)

            if model.presets.isEmpty {
                if model.loadingPresets {
                    ProgressView().tint(Theme.accent).frame(maxWidth: .infinity).padding(.vertical, 12)
                } else {
                    Text("Styles indisponibles")
                        .font(.caption).foregroundStyle(Theme.textSecondary)
                        .frame(maxWidth: .infinity).padding(.vertical, 12)
                }
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(model.presets) { preset in
                            presetChip(preset)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
    }

    private func presetChip(_ preset: CaptionPreset) -> some View {
        let tint = Color(hex: preset.highlight) ?? Theme.accent
        let selected = model.selectedPresetId == preset.id
        return Button {
            model.selectedPresetId = preset.id
        } label: {
            VStack(spacing: 8) {
                // Swatch: the preset's highlight colour, with a sparkle if it "pops".
                ZStack {
                    Circle()
                        .fill(tint)
                        .frame(width: 34, height: 34)
                        .overlay(Circle().strokeBorder(.white.opacity(0.25), lineWidth: 1))
                    if preset.pop {
                        Image(systemName: "sparkles")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundStyle(tint.contrastingForeground)
                    }
                }
                Text(preset.label)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(selected ? Theme.textPrimary : Theme.textSecondary)
            }
            .frame(width: 78)
            .padding(.vertical, 12)
            .forgeGlassCard(cornerRadius: Theme.Radius.sm, selected: selected)
            .overlay {
                if selected {
                    RoundedRectangle(cornerRadius: Theme.Radius.sm)
                        .strokeBorder(tint, lineWidth: 2)
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Style \(preset.label)\(preset.pop ? ", animé" : "")")
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
        .accessibilityIdentifier("editor.preset.\(preset.id)")
    }

    // MARK: - Custom highlight colour

    private let swatches = ["#FFFFFF", "#FFD400", "#00FF66", "#33D9F2", "#FF3DCB", "#FF4D4D"]

    private var colourSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Couleur du mot actif", systemImage: "paintpalette")
                .font(.headline).foregroundStyle(Theme.textPrimary)
            HStack(spacing: 12) {
                // "Auto" = use the preset's own highlight colour.
                Button { model.highlightHex = nil } label: {
                    ZStack {
                        Circle().strokeBorder(Theme.textSecondary, lineWidth: 1.5).frame(width: 30, height: 30)
                        Image(systemName: "a.circle").font(.system(size: 13)).foregroundStyle(Theme.textSecondary)
                    }
                }
                .buttonStyle(.plain)
                .overlay { if model.highlightHex == nil { selectionRing } }
                .accessibilityLabel("Couleur auto (style)")

                ForEach(swatches, id: \.self) { hex in
                    Button { model.highlightHex = hex } label: {
                        Circle().fill(Color(hex: hex) ?? .white).frame(width: 30, height: 30)
                            .overlay(Circle().strokeBorder(.white.opacity(0.25), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .overlay { if model.highlightHex?.caseInsensitiveCompare(hex) == .orderedSame { selectionRing } }
                    .accessibilityLabel("Couleur \(hex)")
                }

                ColorPicker("", selection: Binding(
                    get: { Color(hex: model.highlightHex ?? "#FFFFFF") ?? .white },
                    set: { model.highlightHex = $0.toHex() },
                ), supportsOpacity: false)
                .labelsHidden().frame(width: 30, height: 30)
                .accessibilityLabel("Couleur personnalisée")
            }
        }
        .accessibilityIdentifier("editor.colour")
    }

    private var selectionRing: some View {
        Circle().strokeBorder(Theme.accent, lineWidth: 2.5).frame(width: 37, height: 37)
    }

    // MARK: - Trim

    private var trimSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Rogner", systemImage: "scissors").font(.headline).foregroundStyle(Theme.textPrimary)
                Spacer()
                Text(model.isTrimmed
                     ? "\(timeStr(model.inPoint))–\(timeStr(model.outPoint)) · \(Int((model.outPoint - model.inPoint).rounded()))s"
                     : "Clip entier · \(Int(model.clipDuration.rounded()))s")
                    .font(.caption.monospacedDigit()).foregroundStyle(Theme.textSecondary)
            }
            TrimTrack(duration: model.clipDuration, inPoint: $model.inPoint, outPoint: $model.outPoint)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: Theme.Radius.md)
        .accessibilityIdentifier("editor.trim")
    }

    private func timeStr(_ t: Double) -> String {
        let s = Int(t.rounded()); return String(format: "%d:%02d", s / 60, s % 60)
    }

    // MARK: - Caption text editor

    private var captionSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("Légendes", systemImage: "captions.bubble")
                    .font(.headline).foregroundStyle(Theme.textPrimary)
                Spacer()
                if model.captionsEdited {
                    Text("modifié").font(.caption2.weight(.semibold)).foregroundStyle(Theme.accent)
                }
            }
            Text("Corrige une faute — le rendu garde le timing.")
                .font(.caption).foregroundStyle(Theme.textSecondary)

            if model.captionLines.isEmpty {
                Text("Pas de légendes pour ce clip.")
                    .font(.caption).foregroundStyle(Theme.textSecondary)
                    .frame(maxWidth: .infinity).padding(.vertical, 8)
            } else {
                VStack(spacing: 8) {
                    ForEach($model.captionLines) { $line in
                        HStack(alignment: .top, spacing: 10) {
                            Text(timeStr(line.start))
                                .font(.caption2.monospacedDigit()).foregroundStyle(Theme.textSecondary)
                                .frame(width: 36, alignment: .leading).padding(.top, 2)
                            TextField("Texte", text: $line.text, axis: .vertical)
                                .font(.subheadline).foregroundStyle(Theme.textPrimary)
                                .textFieldStyle(.plain).submitLabel(.done)
                                .accessibilityLabel("Légende à \(timeStr(line.start))")
                        }
                        .padding(.horizontal, 12).padding(.vertical, 9)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.Radius.sm))
                    }
                }
            }
        }
        .accessibilityIdentifier("editor.captions")
    }

    // MARK: - Re-render CTA

    private var rerenderSection: some View {
        Button {
            Task { await model.rerender() }
        } label: {
            Group {
                if model.busy {
                    ProgressView().tint(.white)
                } else {
                    Label("Re-render", systemImage: "wand.and.stars")
                }
            }
            .frame(maxWidth: .infinity)
        }
        .padding()
        .foregroundStyle(.white)
        .forgeGlassAccent(cornerRadius: Theme.Radius.md)
        .opacity(model.canRerender ? 1 : 0.5)
        .disabled(!model.canRerender)
        .accessibilityIdentifier("editor.rerender")
        .accessibilityHint(demo ? "Indisponible en mode démo" : "Relance le rendu du clip avec le style choisi")
    }

    // MARK: - Job progress (reuses JobsSheet row styling)

    private func progressCard(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(job.typeLabel).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.textPrimary)
                Spacer()
                Text(job.statusLabel)
                    .font(.caption2.weight(.semibold)).foregroundStyle(.white)
                    .padding(.horizontal, 7).padding(.vertical, 2)
                    .background(job.statusColor).clipShape(Capsule())
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(job.typeLabel), \(job.statusLabel)")

            if job.isActive {
                ProgressView(value: job.fraction).tint(Theme.accent)
                    .forgeShimmer(active: true)
                HStack {
                    if let stage = job.stage, !stage.isEmpty {
                        Text(stage).font(.caption2).foregroundStyle(Theme.textSecondary)
                    }
                    Spacer()
                    Text("\(Int(job.progress))%").font(.caption2.monospacedDigit()).foregroundStyle(Theme.textSecondary)
                }
            } else if let err = job.error, !err.isEmpty {
                Text(err).font(.caption).foregroundStyle(Theme.danger).lineLimit(2)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: Theme.Radius.md)
    }

    private var successBanner: some View {
        Label("Nouveau rendu prêt — aperçu mis à jour", systemImage: "checkmark.circle.fill")
            .font(.subheadline)
            .foregroundStyle(Theme.success)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .forgeGlassCard(cornerRadius: Theme.Radius.sm)
            .accessibilityIdentifier("editor.success")
    }
}

// MARK: - Model

@MainActor
final class EditorModel: ObservableObject {
    let api: ForgeAPI
    let clip: Clip
    let demo: Bool

    @Published var presets: [CaptionPreset] = []
    @Published var loadingPresets = false
    @Published var selectedPresetId: String?
    @Published var busy = false
    /// The EXPORT job spawned by the last re-render, mirrored from the WS feed.
    @Published var trackedJob: Job?
    @Published var succeeded = false
    @Published var successTick = 0
    @Published var errorTick = 0
    /// Bumped to force a fresh VideoPlayer view after we swap the item.
    @Published var playerGeneration = 0

    /// Clip-relative trim (seconds) + optional custom active-word highlight.
    @Published var inPoint: Double = 0
    @Published var outPoint: Double = 0
    @Published var highlightHex: String?
    /// Editable caption lines + the pristine copy to detect edits.
    @Published var captionLines: [CaptionLine] = []
    private var originalLines: [CaptionLine] = []
    var captionsEdited: Bool { captionLines != originalLines && !originalLines.isEmpty }
    var clipDuration: Double { max(1, clip.duration) }
    /// True once a handle has moved off the full range — only then do we trim.
    var isTrimmed: Bool { inPoint > 0.05 || outPoint < clipDuration - 0.05 }

    private(set) var player: AVPlayer?
    private let socket: ForgeSocket?
    private var trackedJobId: String?
    private var observation: Task<Void, Never>?

    init(api: ForgeAPI, clip: Clip, demo: Bool = false) {
        self.api = api
        self.clip = clip
        self.demo = demo
        self.outPoint = max(1, clip.duration)
        if demo {
            self.player = nil
            self.socket = nil
        } else {
            self.player = Self.makePlayer(api: api, clipId: clip.id, cacheBust: nil)
            self.socket = ForgeSocket(baseURL: api.baseURL, apiKey: api.apiKey)
        }
    }

    /// Re-render is offered only when a preset is chosen and we're not mid-flight
    /// or already tracking an active job — and never in demo (the CTA is inert).
    var canRerender: Bool {
        !demo && selectedPresetId != nil && !busy && !(trackedJob?.isActive ?? false)
    }

    func loadPresets() async {
        if demo {
            presets = DemoData.captionPresets
            selectedPresetId = presets.first?.id
            return
        }
        loadingPresets = true; defer { loadingPresets = false }
        if let fetched = try? await api.captionPresets() {
            presets = fetched
            if selectedPresetId == nil { selectedPresetId = fetched.first?.id }
        }
    }

    func loadCaptions() async {
        guard !demo else { captionLines = DemoData.captionLines; originalLines = captionLines; return }
        if let lines = try? await api.clipCaptions(clipId: clip.id) {
            captionLines = lines
            originalLines = lines
        }
    }

    func rerender() async {
        guard !demo, let presetId = selectedPresetId else { return }
        busy = true; defer { busy = false }
        succeeded = false
        do {
            let jobId = try await api.rerenderClip(
                clipId: clip.id,
                presetId: presetId,
                highlightColorHex: highlightHex,
                trimIn: isTrimmed ? inPoint : nil,
                trimOut: isTrimmed ? outPoint : nil,
                editedCaptions: captionsEdited ? captionLines : nil,
            )
            trackedJobId = jobId
            // Seed a pending row immediately so the UI reacts before the first
            // WS broadcast arrives.
            trackedJob = Job(
                id: jobId, type: "export", projectId: clip.projectId, status: "pending",
                progress: 0, stage: nil, message: nil, error: nil,
                createdAt: ISO8601DateFormatter().string(from: Date()),
                startedAt: nil, completedAt: nil,
            )
            startTracking()
        } catch {
            errorTick += 1
            trackedJob = Job(
                id: "rerender-error", type: "export", projectId: clip.projectId, status: "failed",
                progress: 0, stage: nil, message: nil, error: error.localizedDescription,
                createdAt: ISO8601DateFormatter().string(from: Date()),
                startedAt: nil, completedAt: nil,
            )
        }
    }

    /// Watch the WS live-job feed for our jobId; on completion, swap the player
    /// to the refreshed (cache-busted) video and surface success.
    private func startTracking() {
        guard let socket, let jobId = trackedJobId else { return }
        socket.start()
        observation?.cancel()
        observation = Task { [weak self] in
            // Poll the published map; ForgeSocket mutates it on the main actor on
            // every JOB_UPDATE, so this stays a lightweight, bounded loop.
            for _ in 0..<1800 {   // ~15 min ceiling at 0.5s cadence
                guard let self, !Task.isCancelled else { return }
                if let job = socket.liveJobs[jobId] {
                    self.trackedJob = job
                    if job.status == "completed" {
                        self.handleCompletion()
                        return
                    }
                    if job.status == "failed" || job.status == "cancelled" {
                        self.errorTick += 1
                        return
                    }
                }
                try? await Task.sleep(for: .milliseconds(500))
            }
        }
    }

    private func handleCompletion() {
        // The ClipQueue row's video was replaced in place; refetch it with a
        // cache-busting query so AVPlayer re-downloads instead of serving stale
        // bytes, then bump the generation to remount the VideoPlayer.
        player?.pause()
        player = Self.makePlayer(api: api, clipId: clip.id, cacheBust: trackedJobId)
        playerGeneration += 1
        succeeded = true
        successTick += 1
        player?.play()
    }

    func teardown() {
        observation?.cancel()
        socket?.stop()
        player?.pause()
    }

    private static func makePlayer(api: ForgeAPI, clipId: String, cacheBust: String?) -> AVPlayer {
        var url = api.videoURL(clipId: clipId)
        if let cacheBust,
           var comps = URLComponents(url: url, resolvingAgainstBaseURL: false) {
            comps.queryItems = (comps.queryItems ?? []) + [URLQueryItem(name: "v", value: cacheBust)]
            if let bumped = comps.url { url = bumped }
        }
        // Pass the API key as an HTTP header so AVPlayer authenticates without
        // leaking the key into the URL (matches DetailModel).
        let asset = AVURLAsset(
            url: url,
            options: ["AVURLAssetHTTPHeaderFieldsKey": ["X-API-Key": api.apiKey]],
        )
        return AVPlayer(playerItem: AVPlayerItem(asset: asset))
    }
}

// MARK: - Trim track (dual-handle range slider)

private struct TrimTrack: View {
    let duration: Double
    @Binding var inPoint: Double
    @Binding var outPoint: Double

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let inX = CGFloat(inPoint / duration) * w
            let outX = CGFloat(outPoint / duration) * w
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.surface).frame(height: 6)
                Capsule().fill(Theme.accentGradient)
                    .frame(width: max(2, outX - inX), height: 6).offset(x: inX)
                handle.offset(x: inX - 12).gesture(drag(isIn: true, width: w))
                    .accessibilityLabel("Début du clip, \(Int(inPoint))s")
                handle.offset(x: outX - 12).gesture(drag(isIn: false, width: w))
                    .accessibilityLabel("Fin du clip, \(Int(outPoint))s")
            }
            .frame(height: 24)
            .coordinateSpace(name: "trim")
        }
        .frame(height: 24)
    }

    private var handle: some View {
        Circle().fill(.white).frame(width: 24, height: 24)
            .shadow(color: .black.opacity(0.35), radius: 2, y: 1)
            .overlay(Circle().strokeBorder(Theme.accent, lineWidth: 2.5))
    }

    private func drag(isIn: Bool, width: CGFloat) -> some Gesture {
        DragGesture(coordinateSpace: .named("trim")).onChanged { v in
            let t = max(0, min(duration, Double(v.location.x / max(width, 1)) * duration))
            if isIn { inPoint = min(t, outPoint - 1) } else { outPoint = max(t, inPoint + 1) }
        }
    }
}

// MARK: - Color hex parsing

extension Color {
    /// Parse "#RRGGBB" (or "RRGGBB") into a Color; nil on malformed input.
    init?(hex: String) {
        var s = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.hasPrefix("#") { s.removeFirst() }
        guard s.count == 6, let value = UInt32(s, radix: 16) else { return nil }
        self.init(
            red: Double((value >> 16) & 0xFF) / 255,
            green: Double((value >> 8) & 0xFF) / 255,
            blue: Double(value & 0xFF) / 255,
        )
    }

    /// "#RRGGBB" string for sending a chosen colour to the engine.
    func toHex() -> String {
        let ui = UIColor(self)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        ui.getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "#%02X%02X%02X", Int((r * 255).rounded()), Int((g * 255).rounded()), Int((b * 255).rounded()))
    }

    /// Black or white, whichever reads better on this colour — for the sparkle
    /// glyph sitting on a preset swatch.
    var contrastingForeground: Color {
        let ui = UIColor(self)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        ui.getRed(&r, green: &g, blue: &b, alpha: &a)
        // Rec. 601 luma.
        let luma = 0.299 * r + 0.587 * g + 0.114 * b
        return luma > 0.6 ? .black : .white
    }
}
