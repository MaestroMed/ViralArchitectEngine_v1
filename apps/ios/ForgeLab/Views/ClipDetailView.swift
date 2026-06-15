import AVKit
import SwiftUI

/// Preview + the morning workflow's terminal actions: Download to Photos
/// (with caption copied to clipboard) and Open TikTok. Single Approve / Reject
/// pair as well, because reviewing the clip and deciding usually happens in
/// the same swipe.
struct ClipDetailView: View {
    let api: ForgeAPI
    let clip: Clip
    let demo: Bool
    @Environment(\.dismiss) var dismiss

    @StateObject private var model: DetailModel

    init(api: ForgeAPI, clip: Clip, demo: Bool = false) {
        self.api = api
        self.clip = clip
        self.demo = demo
        _model = StateObject(wrappedValue: DetailModel(api: api, clip: clip, demo: demo))
    }

    var body: some View {
        ScrollView {
            GlassEffectContainer(spacing: 16) {
                VStack(spacing: 16) {
                    playerCard
                    metadata
                    actions
                    if let outcome = model.lastOutcome {
                        OutcomeBanner(outcome: outcome)
                            .transition(.opacity)
                    }
                }
            }
            .padding()
        }
        .background(Theme.background)
        .navigationTitle(clip.title ?? "Clip")
        .navigationBarTitleDisplayMode(.inline)
        .sensoryFeedback(.success, trigger: model.actionCount)
    }

    @ViewBuilder
    private var playerCard: some View {
        if demo || model.player == nil {
            // Demo / no-player: static 9:16 placeholder so screenshots and
            // offline states still look intentional.
            RoundedRectangle(cornerRadius: 20)
                .fill(LinearGradient(
                    colors: [Color(red: 0.09, green: 0.20, blue: 0.31), Color.black],
                    startPoint: .top, endPoint: .bottom,
                ))
                .aspectRatio(9 / 16, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .overlay(Image(systemName: "play.circle.fill").font(.system(size: 56)).foregroundStyle(.white.opacity(0.9)))
        } else if let player = model.player {
            VideoPlayer(player: player)
                .aspectRatio(9 / 16, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .background(Color.black)
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .onAppear { player.play() }
                .onDisappear { player.pause() }
        }
    }

    private var metadata: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                ScoreBadge(score: clip.viralScore)
                Spacer()
                Label(formatDuration(clip.duration), systemImage: "clock")
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
            }
            if let desc = clip.description, !desc.isEmpty {
                Text(desc)
                    .font(.body)
                    .foregroundStyle(Theme.textPrimary)
            }
            if !clip.hashtags.isEmpty {
                HashtagFlow(tags: clip.hashtags.map { $0.hasPrefix("#") ? $0 : "#\($0)" })
            }
        }
        .padding()
        .forgeGlassCard(cornerRadius: 16)
    }

    private var actions: some View {
        VStack(spacing: 12) {
            Button {
                Task { await model.downloadAndOpen() }
            } label: {
                if model.busy { ProgressView().tint(.white) }
                else {
                    Label("Télécharger + ouvrir TikTok", systemImage: "arrow.down.to.line")
                }
            }
            .frame(maxWidth: .infinity)
            .padding()
            .foregroundStyle(.white)
            .forgeGlassAccent(cornerRadius: 16)
            .disabled(model.busy)
            .accessibilityIdentifier("download-button")

            HStack(spacing: 12) {
                Button {
                    Task { await model.reject() }
                } label: {
                    Label("Rejeter", systemImage: "xmark")
                        .frame(maxWidth: .infinity)
                }
                .padding()
                .foregroundStyle(Theme.danger)
                .forgeGlassCard(cornerRadius: 14)
                .disabled(model.busy)

                Button {
                    Task { await model.approve() }
                } label: {
                    Label("Approuver", systemImage: "checkmark")
                        .frame(maxWidth: .infinity)
                }
                .padding()
                .foregroundStyle(Theme.success)
                .forgeGlassCard(cornerRadius: 14)
                .disabled(model.busy)
            }
        }
    }

    private func formatDuration(_ d: Double) -> String {
        let total = Int(d.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }
}

@MainActor
final class DetailModel: ObservableObject {
    let api: ForgeAPI
    let clip: Clip
    /// nil in demo mode (no network player); the view renders a placeholder.
    let player: AVPlayer?
    private let downloader: BundleDownloader

    @Published var busy = false
    @Published var lastOutcome: BundleDownloader.Outcome?
    /// Bumped after each completed action so the view fires haptic feedback.
    @Published var actionCount = 0

    init(api: ForgeAPI, clip: Clip, demo: Bool = false) {
        self.api = api
        self.clip = clip
        if demo {
            self.player = nil
        } else {
            // Pass the API key as an HTTP header so AVPlayer authenticates
            // without leaking credentials into the URL.
            let asset = AVURLAsset(
                url: api.videoURL(clipId: clip.id),
                options: ["AVURLAssetHTTPHeaderFieldsKey": ["X-API-Key": api.apiKey]],
            )
            self.player = AVPlayer(playerItem: AVPlayerItem(asset: asset))
        }
        self.downloader = BundleDownloader(api: api)
    }

    func downloadAndOpen() async {
        busy = true; defer { busy = false }
        do {
            let outcome = try await downloader.saveToPhotosAndShare(clip: clip)
            lastOutcome = outcome
            _ = downloader.openTikTokOrShare(from: nil)
            if outcome.savedToPhotos {
                try? await api.approve(clipId: clip.id)
            }
        } catch {
            lastOutcome = .init(savedToPhotos: false, captionCopied: false,
                                photosError: error.localizedDescription)
        }
        actionCount += 1
    }

    func approve() async {
        busy = true; defer { busy = false }
        try? await api.approve(clipId: clip.id)
        actionCount += 1
    }

    func reject() async {
        busy = true; defer { busy = false }
        try? await api.reject(clipId: clip.id)
        actionCount += 1
    }
}

private struct HashtagFlow: View {
    let tags: [String]
    var body: some View {
        // SwiftUI doesn't ship a true flow layout pre-iOS 17. We get away with
        // it here because hashtags are short — wrap with HStacks of fixed-ish
        // width strings via TextLayoutGuide.
        FlexibleHStack(tags: tags) { tag in
            Text(tag)
                .font(.caption.weight(.semibold))
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Theme.accentSoft)
                .foregroundStyle(Theme.accent)
                .clipShape(Capsule())
        }
    }
}

private struct FlexibleHStack<Content: View>: View {
    let tags: [String]
    @ViewBuilder let content: (String) -> Content
    var body: some View {
        // Naive wrap: iOS 17+ has `Layout` we could use; iOS 17 is our minimum
        // so `Grid` works too. Keep simple: a vertical stack of HStacks bucketed
        // by approximate width — good enough for ≤10 tags.
        VStack(alignment: .leading, spacing: 6) {
            ForEach(rows(), id: \.self) { row in
                HStack(spacing: 6) { ForEach(row, id: \.self) { content($0) } }
            }
        }
    }
    private func rows() -> [[String]] {
        var out: [[String]] = [[]]
        var currentWidth: CGFloat = 0
        let maxWidth: CGFloat = 320
        for tag in tags {
            // Rough char-based width estimate, sufficient for hashtags.
            let w = CGFloat(tag.count) * 8 + 24
            if currentWidth + w > maxWidth {
                out.append([tag]); currentWidth = w
            } else {
                out[out.count - 1].append(tag); currentWidth += w
            }
        }
        return out
    }
}

private struct OutcomeBanner: View {
    let outcome: BundleDownloader.Outcome
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if outcome.savedToPhotos {
                Label("Clip enregistré dans Photos", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(Theme.success)
            }
            if outcome.captionCopied {
                Label("Légende copiée — colle dans TikTok", systemImage: "doc.on.clipboard")
                    .foregroundStyle(Theme.textPrimary)
            }
            if let err = outcome.photosError {
                Label(err, systemImage: "exclamationmark.triangle")
                    .foregroundStyle(Theme.danger)
            }
        }
        .padding()
        .forgeGlassCard(cornerRadius: 14)
    }
}
