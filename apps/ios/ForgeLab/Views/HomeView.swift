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
                VStack(alignment: .leading, spacing: 22) {
                    header
                    heroCard
                    statsRow
                    todaySection
                    engineFooter
                }
                .padding(20)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { settingsOpen = true } label: {
                        Image(systemName: "gearshape.fill").foregroundStyle(Theme.textSecondary)
                    }
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
            Image("BrandMark")
                .resizable().scaledToFit()
                .frame(width: 46, height: 46)
                .accessibilityHidden(true)
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

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text("\(todayClips.isEmpty ? pendingTotal : todayPending)")
                    .font(.system(size: 56, weight: .heavy, design: .rounded))
                    .foregroundStyle(Theme.accent)
                    .contentTransition(.numericText())
                VStack(alignment: .leading, spacing: 0) {
                    Text(todayClips.isEmpty ? "clips en attente" : "clips à reviewer")
                        .font(.headline).foregroundStyle(Theme.textPrimary)
                    Text(todayClips.isEmpty ? "dans la file" : "aujourd'hui")
                        .font(.subheadline).foregroundStyle(Theme.textSecondary)
                }
                Spacer(minLength: 0)
                Image(systemName: (todayPending == 0 && pendingTotal == 0) ? "checkmark.seal.fill" : "sparkles")
                    .font(.largeTitle)
                    .foregroundStyle((todayPending == 0 && pendingTotal == 0) ? Theme.success : Theme.accent)
            }
            Button {
                selectedTab?.wrappedValue = 1
            } label: {
                HStack {
                    Text(pendingTotal > 0 ? "Reviewer la file" : "Ouvrir la file")
                        .font(.subheadline.weight(.semibold))
                    Spacer()
                    Image(systemName: "arrow.right")
                }
                .foregroundStyle(.white)
                .padding(.vertical, 12).padding(.horizontal, 16)
                .frame(maxWidth: .infinity)
                .forgeGlassAccent(cornerRadius: 14)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("home.openQueue")
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: 22)
    }

    // MARK: - Stats

    private var statsRow: some View {
        HStack(spacing: 12) {
            statCard("En attente", summary?.pendingReview ?? 0, "tray.full.fill", Theme.accent)
            statCard("Approuvés", summary?.approved ?? 0, "checkmark.circle.fill", Theme.success)
            statCard("Postés", summary?.published ?? 0, "paperplane.fill", Color(red: 0.4, green: 0.6, blue: 1.0))
        }
    }

    private func statCard(_ label: String, _ value: Int, _ icon: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon).foregroundStyle(color).font(.title3)
            Text("\(value)")
                .font(.title2.weight(.bold).monospacedDigit())
                .foregroundStyle(Theme.textPrimary)
            Text(label).font(.caption).foregroundStyle(Theme.textSecondary)
        }
        .padding(14)
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
                        .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 2)
            }
        }
    }

    private var emptyToday: some View {
        VStack(spacing: 10) {
            Image(systemName: "moon.zzz.fill").font(.largeTitle).foregroundStyle(Theme.textSecondary)
            Text("Aucun clip aujourd'hui").font(.headline).foregroundStyle(Theme.textPrimary)
            Text("Les nouveaux clips d'Eto apparaîtront ici dès qu'une VOD est traitée.")
                .font(.subheadline).foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(28)
        .forgeGlassCard(cornerRadius: 18)
    }

    // MARK: - Engine status

    private var engineFooter: some View {
        HStack(spacing: 8) {
            Circle().fill(engineVersion != nil ? Theme.success : Theme.danger).frame(width: 8, height: 8)
            Text(engineVersion != nil ? "Moteur connecté · v\(engineVersion!)" : "Moteur injoignable")
                .font(.caption).foregroundStyle(Theme.textSecondary)
            Spacer()
            if let error { Text(error).font(.caption2).foregroundStyle(Theme.danger).lineLimit(1) }
        }
        .padding(.horizontal, 4)
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
                    ScoreBadge(score: clip.viralScore).padding(8)
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
                [Color(red: 0.36, green: 0.13, blue: 0.19), Color(red: 0.10, green: 0.04, blue: 0.06)],
                [Color(red: 0.11, green: 0.23, blue: 0.42), Color(red: 0.04, green: 0.09, blue: 0.19)],
                [Color(red: 0.14, green: 0.27, blue: 0.20), Color(red: 0.05, green: 0.10, blue: 0.08)],
                [Color(red: 0.30, green: 0.22, blue: 0.06), Color(red: 0.10, green: 0.07, blue: 0.02)],
            ]
            let idx = abs(clip.id.hashValue) % palettes.count
            LinearGradient(colors: palettes[idx], startPoint: .topLeading, endPoint: .bottomTrailing)
                .overlay(Image(systemName: "play.fill").foregroundStyle(.white.opacity(0.85)).font(.title))
        } else {
            AsyncImage(url: api.coverURL(clipId: clip.id)) { phase in
                switch phase {
                case .success(let img): img.resizable().aspectRatio(contentMode: .fill)
                case .failure: Rectangle().fill(Theme.surface).overlay(Image(systemName: "photo").foregroundStyle(Theme.textSecondary))
                default: Rectangle().fill(Theme.surface).overlay(ProgressView())
                }
            }
        }
    }

    private func formatDuration(_ d: Double) -> String {
        let t = Int(d.rounded()); return String(format: "%d:%02d", t / 60, t % 60)
    }
}
