import SwiftUI

/// Dashboard landing screen — "superbe homepage" focused on TODAY.
/// Shows the brand, today's date, a hero review-status card, queue stats, and a
/// carousel of today's clips. Falls back gracefully when today is empty or the
/// engine is unreachable. Defaults to today's clips (clips/by-date).
struct HomeView: View {
    let api: ForgeAPI
    /// When set, render these instead of networking (--demo / previews).
    var demoClips: [Clip]? = nil
    /// Lets the hero CTA jump to the Clips tab.
    var selectedTab: Binding<Int>? = nil
    @EnvironmentObject var settings: Settings

    @State private var todayClips: [Clip] = []
    @State private var summary: QueueSummaryResponse?
    @State private var engineVersion: String?
    @State private var loading = false
    @State private var error: String?
    @State private var settingsOpen = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    header
                    meshHero
                    bentoRow
                    todaySection
                    engineFooter
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 20)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { settingsOpen = true } label: {
                        Image(systemName: "gearshape.fill").foregroundStyle(Theme.textSecondary)
                    }
                    .accessibilityLabel("Réglages")
                    .accessibilityIdentifier("home.settings")
                }
            }
            .sheet(isPresented: $settingsOpen) { NavigationStack { SettingsView() } }
            .refreshable { await load() }
            .task { await load() }
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 14) {
            BrandMark(size: 44)
            VStack(alignment: .leading, spacing: 2) {
                Text("VIRAL ARCHITECT ENGINE")
                    .font(.caption2.weight(.bold))
                    .tracking(1.5)
                    .foregroundStyle(Theme.accent)
                Text(greeting)
                    .font(.title.weight(.bold))
                    .foregroundStyle(Theme.textPrimary)
                Text(Self.todayLong)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textSecondary)
            }
            Spacer(minLength: 0)
        }
    }

    // MARK: - Hero review card

    private var pendingTotal: Int { summary?.pendingReview ?? todayClips.filter { $0.status == "pending_review" }.count }
    private var todayPending: Int { todayClips.filter { $0.status == "pending_review" }.count }

    private var heroCount: Int { todayClips.isEmpty ? pendingTotal : todayPending }
    private var allCaughtUp: Bool { heroCount == 0 }

    private var heroEyebrow: String {
        if allCaughtUp { return "Tout est à jour" }
        return todayClips.isEmpty ? "Dans la file" : "À reviewer aujourd'hui"
    }
    private var heroSubtitle: String {
        allCaughtUp ? "Aucun clip en attente — beau boulot 🎉"
                    : "Swipe pour trier, exporte les meilleurs."
    }

    private var meshHero: some View {
        ZStack(alignment: .topLeading) {
            AnimatedMeshHero()
            LinearGradient(colors: [.black.opacity(0.05), .black.opacity(0.32)],
                           startPoint: .top, endPoint: .bottom)
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    Text(heroEyebrow)
                        .font(.caption.weight(.bold)).tracking(1.3)
                        .foregroundStyle(.white.opacity(0.9)).textCase(.uppercase)
                    Spacer()
                    Image(systemName: allCaughtUp ? "checkmark.seal.fill" : "sparkles")
                        .font(.system(size: 26, weight: .semibold)).foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.25), radius: 6)
                }
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text("\(heroCount)")
                        .font(.system(size: 66, weight: .heavy, design: .rounded))
                        .foregroundStyle(.white).contentTransition(.numericText())
                        .shadow(color: .black.opacity(0.25), radius: 8, y: 2)
                    if !allCaughtUp {
                        Text("clips").font(.title3.weight(.semibold)).foregroundStyle(.white.opacity(0.92))
                    }
                }
                Text(heroSubtitle).font(.subheadline.weight(.medium)).foregroundStyle(.white.opacity(0.92))
                Spacer(minLength: 16)
                Button {
                    selectedTab?.wrappedValue = 3   // Clips tab (Pilote=1, Sources=2)
                } label: {
                    HStack {
                        Text(allCaughtUp ? "Ouvrir la file" : "Reviewer maintenant")
                            .font(.subheadline.weight(.bold))
                        Spacer()
                        Image(systemName: "arrow.right").font(.subheadline.weight(.bold))
                    }
                    .foregroundStyle(Theme.accentDeep)
                    .padding(.vertical, 13).padding(.horizontal, 18)
                    .frame(maxWidth: .infinity)
                    .background(.white, in: Capsule())
                    .shadow(color: .black.opacity(0.15), radius: 8, y: 3)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("home.openQueue")
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(22)
        }
        .frame(maxWidth: .infinity).frame(height: 236)
        .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 30, style: .continuous).stroke(.white.opacity(0.14), lineWidth: 1))
        .shadow(color: Theme.accent.opacity(0.4), radius: 22, y: 12)
        .animation(.easeInOut, value: heroCount)
    }

    // MARK: - Stats

    /// Highest-scoring clip of the day — the "top du jour" feature.
    private var topClip: Clip? {
        let pending = todayClips.filter { $0.status == "pending_review" }
        return (pending.isEmpty ? todayClips : pending).max(by: { $0.viralScore < $1.viralScore })
    }

    /// Asymmetric "bento": a tall feature cell beside stacked stat tiles.
    private var bentoRow: some View {
        HStack(alignment: .top, spacing: 12) {
            featureCell
            VStack(spacing: 12) {
                statTile("En attente", summary?.pendingReview ?? 0, "tray.full.fill", Theme.accent)
                statTile("Approuvés", summary?.approved ?? 0, "checkmark.circle.fill", Theme.success)
                statTile("Postés", summary?.published ?? 0, "paperplane.fill", Theme.accentBright)
            }
            .frame(width: 124)
        }
    }

    @ViewBuilder
    private var featureCell: some View {
        if let clip = topClip {
            NavigationLink {
                ClipDetailView(api: api, clip: clip, demo: demoClips != nil)
            } label: {
                featureCard(clip)
            }
            .buttonStyle(PressableCardStyle())
        } else {
            VStack(spacing: 8) {
                Image(systemName: "wand.and.stars").font(.title).foregroundStyle(Theme.accent)
                Text("Pas de clip à la une").font(.subheadline).foregroundStyle(Theme.textSecondary)
            }
            .frame(maxWidth: .infinity).frame(height: 232).forgeGlassCard(cornerRadius: 20)
        }
    }

    private func featureCard(_ clip: Clip) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            featureCover(clip)
                .frame(height: 158)
                .frame(maxWidth: .infinity)
                .clipped()
                .overlay(alignment: .topTrailing) { ScoreRing(score: clip.viralScore).padding(10) }
                .overlay(alignment: .topLeading) {
                    Text("TOP DU JOUR").font(.caption2.weight(.bold)).tracking(1)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(Theme.accent, in: Capsule()).padding(10)
                }
            VStack(alignment: .leading, spacing: 4) {
                Text(clip.title ?? "Clip \(clip.id.prefix(6))")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(Theme.textPrimary)
                    .lineLimit(2).multilineTextAlignment(.leading)
                if let ch = clip.channelName {
                    Text(ch).font(.caption2).foregroundStyle(Theme.textSecondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
        }
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(.white.opacity(0.08), lineWidth: 1))
    }

    @ViewBuilder
    private func featureCover(_ clip: Clip) -> some View {
        if demoClips != nil {
            LinearGradient(colors: [Theme.accentDeep, Theme.accent], startPoint: .topLeading, endPoint: .bottomTrailing)
                .overlay(Image(systemName: "play.fill").font(.title).foregroundStyle(.white.opacity(0.9)))
        } else {
            RemoteImage(url: api.coverURL(clipId: clip.id), api: api) {
                Rectangle().fill(Theme.background).overlay(Image(systemName: "photo").foregroundStyle(Theme.textSecondary))
            }
        }
    }

    private func statTile(_ label: String, _ value: Int, _ icon: String, _ color: Color) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).foregroundStyle(color).font(.subheadline).frame(width: 22)
            VStack(alignment: .leading, spacing: 0) {
                Text("\(value)").font(.title3.weight(.bold).monospacedDigit()).foregroundStyle(Theme.textPrimary)
                Text(label).font(.caption2).foregroundStyle(Theme.textSecondary)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12).padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: 16)
    }

    // MARK: - Today's clips carousel

    @ViewBuilder
    private var todaySection: some View {
        HStack {
            Text("Aujourd'hui").font(.title3.weight(.bold)).foregroundStyle(Theme.textPrimary)
            Spacer()
            if !todayClips.isEmpty {
                Text("\(todayClips.count)").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.textSecondary)
            }
        }
        if loading && todayClips.isEmpty {
            ProgressView().frame(maxWidth: .infinity).padding(.vertical, 30)
        } else if todayClips.isEmpty {
            emptyToday
        } else {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 14) {
                    ForEach(todayClips) { clip in
                        NavigationLink {
                            ClipDetailView(api: api, clip: clip, demo: demoClips != nil)
                        } label: {
                            HomePosterCard(clip: clip, api: api, demo: demoClips != nil)
                        }
                        .buttonStyle(PressableCardStyle())
                    }
                }
                .padding(.vertical, 2)
            }
        }
    }

    private var emptyToday: some View {
        EmptyStateCard(
            icon: "moon.zzz.fill",
            title: "Aucun clip aujourd'hui",
            message: "Les nouveaux clips d'Eto apparaîtront ici dès qu'une VOD est traitée.",
        )
    }

    // MARK: - Engine status

    @ViewBuilder
    private var engineFooter: some View {
        if demoClips == nil && !loading && engineVersion == nil {
            // Unreachable: a real recovery card, not a dead-end status line.
            EngineErrorCard(
                onRetry: { Task { await load() } },
                onSettings: { settingsOpen = true }
            )
            .padding(.top, 4)
        } else {
            HStack(spacing: 8) {
                Circle().fill(engineVersion != nil ? Theme.success : Theme.danger).frame(width: 8, height: 8)
                Text(engineVersion.map { "Moteur connecté · v\($0)" } ?? "Moteur injoignable")
                    .font(.caption).foregroundStyle(Theme.textSecondary)
                Spacer()
                if let error { Text(error).font(.caption2).foregroundStyle(Theme.danger).lineLimit(1) }
            }
            .padding(.horizontal, 4)
        }
    }

    // MARK: - Data

    private func load() async {
        if let demo = demoClips {
            todayClips = demo
            summary = QueueSummaryResponse(
                counts: ["pending_review": demo.filter { $0.status == "pending_review" }.count,
                         "approved": demo.filter { $0.status == "approved" }.count,
                         "published": 0],
                total: demo.count)
            engineVersion = "demo"
            return
        }
        loading = true; error = nil
        defer { loading = false }
        // Engine status (best-effort)
        engineVersion = (try? await api.request(HealthResponse.self, path: "/health", needsAuth: false))?.version
        async let s = try? await api.queueSummary()
        async let t = try? await api.clipsByDate(Date())
        summary = await s
        if let resp = await t { todayClips = resp.items }
        else if engineVersion == nil { error = "Connexion au moteur impossible" }
    }

    // MARK: - Formatting

    private var greeting: String {
        let h = Calendar.current.component(.hour, from: Date())
        switch h {
        case 5..<12: return "Bonjour 👋"
        case 12..<18: return "Bon aprèm 👋"
        default: return "Bonsoir 👋"
        }
    }

    private static let todayLong: String = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateFormat = "EEEE d MMMM"
        return f.string(from: Date()).capitalized(with: Locale(identifier: "fr_FR"))
    }()
}

/// Poster-style clip card for the home carousel: 9:16 cover, score badge, title.
struct HomePosterCard: View {
    let clip: Clip
    let api: ForgeAPI
    var demo: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            cover
                .frame(width: 150, height: 200)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(alignment: .topLeading) {
                    ScoreBadge(score: clip.viralScore, large: true).padding(8)
                }
                .overlay(alignment: .bottomTrailing) {
                    Text(formatDuration(clip.duration))
                        .font(.caption2.weight(.semibold).monospacedDigit())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(.black.opacity(0.55)).clipShape(Capsule())
                        .padding(8)
                }
            Text(clip.title ?? "Clip \(clip.id.prefix(6))")
                .font(.caption.weight(.medium))
                .foregroundStyle(Theme.textPrimary)
                .lineLimit(2)
                .frame(width: 150, alignment: .leading)
        }
    }

    @ViewBuilder
    private var cover: some View {
        if demo {
            let palettes: [[Color]] = [
                [Color(red: 0.10, green: 0.27, blue: 0.30), Color(red: 0.04, green: 0.10, blue: 0.11)],
                [Color(red: 0.11, green: 0.23, blue: 0.42), Color(red: 0.04, green: 0.09, blue: 0.19)],
                [Color(red: 0.14, green: 0.27, blue: 0.20), Color(red: 0.05, green: 0.10, blue: 0.08)],
                [Color(red: 0.14, green: 0.14, blue: 0.34), Color(red: 0.05, green: 0.05, blue: 0.13)],
            ]
            let idx = abs(clip.id.hashValue) % palettes.count
            LinearGradient(colors: palettes[idx], startPoint: .topLeading, endPoint: .bottomTrailing)
                .overlay(Image(systemName: "play.fill").foregroundStyle(.white.opacity(0.85)).font(.title))
        } else {
            RemoteImage(url: api.coverURL(clipId: clip.id), api: api) {
                Rectangle().fill(Theme.surface)
                    .overlay(Image(systemName: "photo").foregroundStyle(Theme.textSecondary))
            }
        }
    }

    private func formatDuration(_ d: Double) -> String {
        let t = Int(d.rounded()); return String(format: "%d:%02d", t / 60, t % 60)
    }
}
