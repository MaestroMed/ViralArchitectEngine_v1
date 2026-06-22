import AVKit
import SwiftUI

/// Full-screen "Morning Review" deck: one clip at a time, swipe-right to
/// approve / swipe-left to reject / tap to export, then advance. Collapses the
/// tap→detail→decide→back→next loop into one gesture per clip.
struct TriageDeckView: View {
    let api: ForgeAPI
    let clips: [Clip]
    var demo: Bool = false
    /// Called when the deck is exhausted or closed, with how many were approved.
    var onFinish: (Int) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var index = 0
    @State private var drag: CGSize = .zero
    @State private var player: AVPlayer?
    @State private var approvedCount = 0
    @State private var exportedIds: Set<String> = []
    @State private var busy = false
    @State private var decidingClipId: String?   // re-entrancy guard during fly-away
    @State private var decisionTick = 0          // success haptic
    @State private var rejectTick = 0            // warning haptic

    private var locked: Bool { busy || decidingClipId != nil }

    private let swipeThreshold: CGFloat = 130

    private var current: Clip? { index < clips.count ? clips[index] : nil }
    private var next: Clip? { index + 1 < clips.count ? clips[index + 1] : nil }

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            VStack(spacing: 16) {
                header
                if let current {
                    cardStack(current)
                    actionBar
                } else {
                    finishedState
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 12)
        }
        .task(id: current?.id) { await preparePlayer() }
        .onDisappear { player?.pause() }
        .sensoryFeedback(.success, trigger: decisionTick)
        .sensoryFeedback(.warning, trigger: rejectTick)
    }

    // MARK: Header

    private var header: some View {
        HStack {
            Button { finish() } label: {
                Image(systemName: "xmark").font(.headline).foregroundStyle(Theme.textSecondary)
                    .padding(10).background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel("Fermer le tri")
            Spacer()
            if !clips.isEmpty {
                Text("\(min(index + 1, clips.count)) / \(clips.count)")
                    .font(.subheadline.weight(.semibold).monospacedDigit())
                    .foregroundStyle(Theme.textPrimary)
            }
            Spacer()
            // Symmetry spacer so the counter stays centred.
            Image(systemName: "xmark").font(.headline).opacity(0).padding(10)
        }
    }

    // MARK: Card stack

    private func cardStack(_ clip: Clip) -> some View {
        ZStack {
            if let next {
                clipCard(next, isTop: false)
                    .scaleEffect(0.94)
                    .offset(y: 18)
                    .opacity(0.6)
            }
            clipCard(clip, isTop: true)
                .offset(drag)
                .rotationEffect(.degrees(Double(drag.width / 18)))
                .overlay(decisionOverlay)
                .gesture(
                    DragGesture()
                        .onChanged { if !locked { drag = $0.translation } }
                        .onEnded { if !locked { handleDragEnd($0.translation) } }
                )
                .animation(.spring(response: 0.35, dampingFraction: 0.8), value: drag)
        }
        .frame(maxWidth: .infinity)
    }

    private func clipCard(_ clip: Clip, isTop: Bool) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            player9x16(clip, isTop: isTop)
                .overlay(alignment: .topLeading) {
                    ScoreBadge(score: clip.viralScore, large: true).padding(12)
                }
                .overlay(alignment: .bottom) {
                    LinearGradient(colors: [.clear, .black.opacity(0.75)], startPoint: .center, endPoint: .bottom)
                        .frame(height: 120).allowsHitTesting(false)
                    VStack(alignment: .leading, spacing: 6) {
                        Text(clip.title ?? "Clip \(clip.id.prefix(6))")
                            .font(.headline).foregroundStyle(.white).lineLimit(2)
                        if let desc = clip.description, !desc.isEmpty {
                            Text(desc).font(.subheadline).foregroundStyle(.white.opacity(0.85)).lineLimit(2)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                }
        }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(.white.opacity(0.08), lineWidth: 1))
        .shadow(color: .black.opacity(isTop ? 0.4 : 0), radius: 16, y: 8)
    }

    @ViewBuilder
    private func player9x16(_ clip: Clip, isTop: Bool) -> some View {
        if !demo, isTop, let player {
            VideoPlayer(player: player)
                .aspectRatio(9 / 16, contentMode: .fit)
                .background(Color.black)
                .onAppear { player.play() }
        } else {
            // Back card + demo: deterministic gradient placeholder.
            let palettes: [[Color]] = [
                [Color(red: 0.20, green: 0.10, blue: 0.28), Color.black],
                [Color(red: 0.10, green: 0.20, blue: 0.30), Color.black],
                [Color(red: 0.20, green: 0.10, blue: 0.28), Color.black],
            ]
            let idx = abs(clip.id.hashValue) % palettes.count
            LinearGradient(colors: palettes[idx], startPoint: .top, endPoint: .bottom)
                .aspectRatio(9 / 16, contentMode: .fit)
                .overlay(Image(systemName: "play.circle.fill").font(.system(size: 54)).foregroundStyle(.white.opacity(0.85)))
        }
    }

    /// Green ✓ / red ✗ stamp that fades in as the card is dragged.
    @ViewBuilder
    private var decisionOverlay: some View {
        let progress = min(abs(drag.width) / swipeThreshold, 1)
        let approving = drag.width > 0
        Image(systemName: approving ? "checkmark.circle.fill" : "xmark.circle.fill")
            .font(.system(size: 88, weight: .bold))
            .foregroundStyle(approving ? Theme.success : Theme.danger)
            .opacity(drag.width == 0 ? 0 : Double(progress))
            .rotationEffect(.degrees(approving ? -12 : 12))
    }

    // MARK: Action bar

    private var actionBar: some View {
        HStack(spacing: 14) {
            circleButton("xmark", Theme.danger) { decide(approve: false) }
                .accessibilityLabel("Rejeter")
            Button { Task { await export() } } label: {
                HStack(spacing: 8) {
                    Image(systemName: exportedIds.contains(current?.id ?? "") ? "checkmark" : "square.and.arrow.down")
                    Text(exportedIds.contains(current?.id ?? "") ? "Exporté" : "Exporter")
                }
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity).padding(.vertical, 14)
            }
            .buttonStyle(.glassProminent).tint(Theme.accent)
            .opacity(locked ? 0.6 : 1).disabled(locked)
            circleButton("checkmark", Theme.success) { decide(approve: true) }
                .accessibilityLabel("Approuver")
        }
    }

    private func circleButton(_ icon: String, _ color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon).font(.title2.weight(.bold)).foregroundStyle(color)
                .frame(width: 58, height: 58).background(color.opacity(0.14), in: Circle())
                .overlay(Circle().stroke(color.opacity(0.4), lineWidth: 1))
        }
        .disabled(locked)
    }

    private var finishedState: some View {
        VStack(spacing: 14) {
            Spacer()
            Image(systemName: "checkmark.seal.fill").font(.system(size: 64)).foregroundStyle(Theme.success)
            Text("File vidée 🎉").font(.title2.weight(.bold)).foregroundStyle(Theme.textPrimary)
            Text("\(approvedCount) approuvé\(approvedCount > 1 ? "s" : "") · \(exportedIds.count) exporté\(exportedIds.count > 1 ? "s" : "")")
                .font(.subheadline).foregroundStyle(Theme.textSecondary)
            Button { finish() } label: {
                Text("Terminer").font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 14)
            }
            .buttonStyle(.glassProminent).tint(Theme.accent).padding(.top, 8)
            Spacer()
        }
    }

    // MARK: Logic

    private func handleDragEnd(_ translation: CGSize) {
        if translation.width > swipeThreshold {
            flyAway(approve: true)
        } else if translation.width < -swipeThreshold {
            flyAway(approve: false)
        } else {
            drag = .zero
        }
    }

    private func flyAway(approve: Bool) {
        withAnimation(.easeOut(duration: 0.25)) {
            drag = CGSize(width: approve ? 600 : -600, height: 0)
        }
        decide(approve: approve)
    }

    private func decide(approve: Bool) {
        guard let clip = current, !locked else { return }   // one decision per card
        decidingClipId = clip.id
        if approve { approvedCount += 1; decisionTick += 1 } else { rejectTick += 1 }
        Task {
            if !demo {
                if approve { try? await api.approve(clipId: clip.id) }
                else { try? await api.reject(clipId: clip.id) }
            }
        }
        advance()
    }

    private func advance() {
        player?.pause()
        player = nil   // release the old player before the next card prepares one
        // small delay lets the fly-away animation read before the next card snaps in
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
            decidingClipId = nil
            drag = .zero
            index += 1
        }
    }

    /// Export the current clip, then advance (export auto-approves on save).
    private func export() async {
        guard let clip = current, !locked else { return }
        if demo {
            exportedIds.insert(clip.id); decisionTick += 1
            advance(); return
        }
        busy = true
        let downloader = BundleDownloader(api: api)
        if let outcome = try? await downloader.saveToPhotosAndShare(clip: clip), outcome.savedToPhotos {
            exportedIds.insert(clip.id)
            approvedCount += 1
            decisionTick += 1
            try? await api.approve(clipId: clip.id)
        }
        busy = false
        advance()
    }

    private func preparePlayer() async {
        player?.pause()
        player = nil
        guard !demo, let clip = current else { return }
        let asset = AVURLAsset(
            url: api.videoURL(clipId: clip.id),
            options: ["AVURLAssetHTTPHeaderFieldsKey": ["X-API-Key": api.apiKey]],
        )
        player = AVPlayer(playerItem: AVPlayerItem(asset: asset))
    }

    private func finish() {
        player?.pause()
        onFinish(approvedCount)
        dismiss()
    }
}
