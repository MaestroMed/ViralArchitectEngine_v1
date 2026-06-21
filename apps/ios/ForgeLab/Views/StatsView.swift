import SwiftUI
import Charts

/// Glanceable performance: KPI cards, a clip-production trend, and the top clips
/// by viral score. Read-only, poll-based (battery-friendly). External view /
/// engagement metrics show 0 ("à venir") until a publisher records them.
struct StatsView: View {
    let api: ForgeAPI
    var demoDashboard: AnalyticsDashboard? = nil
    @EnvironmentObject var settings: Settings

    @State private var dashboard: AnalyticsDashboard?
    @State private var days = 30
    @State private var loading = false
    @State private var loadFailed = false
    @State private var settingsOpen = false

    private var isDemo: Bool { demoDashboard != nil }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    rangePicker
                    if let d = dashboard {
                        kpiGrid(d.overview)
                        productionCard(d.trends)
                        topClipsSection(d.topClips)
                    } else if loading {
                        ProgressView().frame(maxWidth: .infinity).padding(.vertical, 60)
                    } else {
                        emptyState
                    }
                }
                .padding(.horizontal)
                .padding(.top, 4)
                .padding(.bottom, 16)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Stats")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { settingsOpen = true } label: {
                        Image(systemName: "gearshape.fill").foregroundStyle(Theme.textSecondary)
                    }
                    .accessibilityLabel("Réglages")
                }
            }
            .sheet(isPresented: $settingsOpen) { NavigationStack { SettingsView() } }
            .refreshable { await load() }
            .task(id: days) { await load() }
            .sensoryFeedback(.selection, trigger: days)   // tactile on range change
        }
    }

    // MARK: Range

    private var rangePicker: some View {
        Picker("Période", selection: $days) {
            Text("7 j").tag(7)
            Text("30 j").tag(30)
            Text("90 j").tag(90)
        }
        .pickerStyle(.segmented)
        .accessibilityIdentifier("stats.range")
    }

    // MARK: KPIs

    private func kpiGrid(_ o: AnalyticsOverview) -> some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
            kpi("Clips", "\(o.totalClips)", "rectangle.stack.fill", Theme.accent, sub: "\(o.clipsLast7Days) cette semaine")
            kpi("Score moyen", String(format: "%.0f", o.avgViralScore), "flame.fill", Theme.scoreColor(o.avgViralScore), sub: "top \(Int(o.topViralScore))")
            kpi("Publiés", "\(o.published)", "paperplane.fill", Theme.success, sub: "\(o.approved) approuvés")
            kpi("Vues", o.totalViews > 0 ? "\(o.totalViews)" : "—", "eye.fill", Color(red: 0.4, green: 0.6, blue: 1.0),
                sub: o.totalViews > 0 ? "\(o.totalEngagement) engagements" : "à venir")
        }
    }

    private func kpi(_ label: String, _ value: String, _ icon: String, _ color: Color, sub: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: icon).foregroundStyle(color).font(.title3)
                Spacer()
            }
            Text(value).font(.title.weight(.bold).monospacedDigit()).foregroundStyle(Theme.textPrimary)
            Text(label).font(.subheadline).foregroundStyle(Theme.textPrimary)
            Text(sub).font(.caption2).foregroundStyle(Theme.textSecondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: 18)
    }

    // MARK: Production trend (Swift Charts)

    private func productionCard(_ trends: AnalyticsTrends) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Production")
            if trends.points.isEmpty {
                Text("Aucun clip sur la période.").font(.subheadline).foregroundStyle(Theme.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .center).padding(.vertical, 24)
            } else {
                Chart(trends.points) { point in
                    BarMark(
                        x: .value("Jour", point.shortLabel),
                        y: .value("Clips", point.clips),
                    )
                    .foregroundStyle(Theme.accentGradient)
                    .cornerRadius(4)
                }
                .chartYAxis { AxisMarks(position: .leading) }
                .frame(height: 160)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: 18)
    }

    // MARK: Top clips

    private func topClipsSection(_ clips: [TopClip]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Top clips")
            if clips.isEmpty {
                Text("Aucun clip.").font(.subheadline).foregroundStyle(Theme.textSecondary)
            } else {
                GlassEffectContainer(spacing: 10) {
                    VStack(spacing: 10) {
                        ForEach(Array(clips.enumerated()), id: \.element.id) { idx, clip in
                            NavigationLink {
                                ClipDetailView(api: api, clip: clip.asClip, demo: isDemo)
                            } label: {
                                topClipRow(rank: idx + 1, clip: clip)
                            }
                            .buttonStyle(PressableCardStyle())
                            .accessibilityIdentifier("topclip-\(clip.id)")
                        }
                    }
                }
            }
        }
    }

    private func topClipRow(rank: Int, clip: TopClip) -> some View {
        HStack(spacing: 12) {
            Text("\(rank)")
                .font(.headline.weight(.bold).monospacedDigit())
                .foregroundStyle(rank <= 3 ? Theme.accent : Theme.textSecondary)
                .frame(width: 22, alignment: .center)
            cover(clip)
                .frame(width: 56, height: 32)
                .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                Text(clip.title ?? "Clip \(clip.clipId.prefix(6))")
                    .font(.subheadline.weight(.medium)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                HStack(spacing: 8) {
                    Text(clip.durationLabel).font(.caption2.monospacedDigit()).foregroundStyle(Theme.textSecondary)
                    if let ch = clip.channelName { Text(ch).font(.caption2).foregroundStyle(Theme.textSecondary) }
                }
            }
            Spacer(minLength: 0)
            ScoreBadge(score: clip.viralScore)
        }
        .padding(10)
        .forgeGlassCard(cornerRadius: 14)
    }

    @ViewBuilder
    private func cover(_ clip: TopClip) -> some View {
        if isDemo {
            LinearGradient(colors: [Theme.accent.opacity(0.5), Theme.surface],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
                .overlay(Image(systemName: "play.fill").font(.caption2).foregroundStyle(.white.opacity(0.8)))
        } else {
            RemoteImage(url: api.coverURL(clipId: clip.clipId), api: api) {
                Rectangle().fill(Theme.background)
                    .overlay(Image(systemName: "photo").font(.caption2).foregroundStyle(Theme.textSecondary))
            }
        }
    }

    @ViewBuilder
    private var emptyState: some View {
        if loadFailed {
            EngineErrorCard(
                title: "Stats indisponibles",
                onRetry: { Task { await load() } },
                onSettings: { settingsOpen = true },
            )
        } else {
            EmptyStateCard(
                icon: "chart.bar",
                title: "Pas encore de stats",
                message: "Les statistiques apparaîtront dès qu'il y a des clips.",
            )
        }
    }

    // MARK: Data

    private func load() async {
        if let demoDashboard {
            dashboard = demoDashboard
            return
        }
        loading = true; loadFailed = false
        defer { loading = false }
        do {
            dashboard = try await api.fetchDashboard(days: days)
        } catch {
            loadFailed = true
        }
    }
}

private extension TopClip {
    /// Build a minimal `Clip` so the row can open the existing detail view.
    var asClip: Clip {
        Clip(
            id: clipId, projectId: projectId ?? "", segmentId: segmentId ?? "",
            title: title, description: nil, hashtags: [], coverPath: nil,
            duration: duration, viralScore: viralScore, status: status,
            channelName: channelName, createdAt: createdAt ?? "",
        )
    }
}
