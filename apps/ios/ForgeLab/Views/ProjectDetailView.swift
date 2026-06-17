import SwiftUI

/// Read-only project deep-dive: source frame, lifecycle status, full metadata,
/// and recent jobs for this project. No triggers, no admin — monitoring only.
struct ProjectDetailView: View {
    let api: ForgeAPI
    let project: Project
    var demo: Bool = false

    @State private var jobs: [Job] = []
    @State private var jobsLoaded = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                hero
                metadataCard
                if let url = project.metadata?.importUrl, let link = URL(string: url) {
                    sourceLink(link, raw: url)
                }
                jobsSection
            }
            .padding()
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("Projet")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadJobs() }
    }

    // MARK: Hero

    private var hero: some View {
        VStack(alignment: .leading, spacing: 0) {
            thumbnail
                .frame(maxWidth: .infinity)
                .frame(height: 200)
                .clipped()
                .overlay(alignment: .bottomLeading) {
                    LinearGradient(colors: [.black.opacity(0.0), .black.opacity(0.75)],
                                   startPoint: .top, endPoint: .bottom)
                        .frame(height: 90)
                        .frame(maxHeight: .infinity, alignment: .bottom)
                        .allowsHitTesting(false)
                    VStack(alignment: .leading, spacing: 6) {
                        Text(project.name)
                            .font(.headline).foregroundStyle(.white)
                            .lineLimit(2)
                        HStack(spacing: 8) {
                            statusPill
                            if let p = project.platformLabel {
                                Text(p).font(.caption).foregroundStyle(.white.opacity(0.85))
                            }
                            if let d = project.durationLabel {
                                Text(d).font(.caption.monospacedDigit()).foregroundStyle(.white.opacity(0.85))
                            }
                        }
                    }
                    .padding(14)
                }
        }
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    @ViewBuilder
    private var thumbnail: some View {
        if demo {
            LinearGradient(colors: [Color(red: 0.20, green: 0.10, blue: 0.28), Color(red: 0.05, green: 0.03, blue: 0.09)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
                .overlay(Image(systemName: "film.stack").foregroundStyle(.white.opacity(0.7)).font(.largeTitle))
        } else {
            RemoteImage(url: api.projectThumbnailURL(projectId: project.id, width: 960, height: 540), api: api) {
                Rectangle().fill(Theme.surface)
                    .overlay(Image(systemName: "film").foregroundStyle(Theme.textSecondary))
            }
        }
    }

    private var statusPill: some View {
        HStack(spacing: 4) {
            Circle().fill(project.statusColor).frame(width: 6, height: 6)
            Text(project.statusLabel).font(.caption.weight(.semibold)).foregroundStyle(.white)
        }
        .padding(.horizontal, 8).padding(.vertical, 3)
        .background(.black.opacity(0.35)).clipShape(Capsule())
    }

    // MARK: Metadata

    private var metadataCard: some View {
        VStack(spacing: 0) {
            if let s = project.segmentsCount { row("Segments", "\(s)") }
            if let avg = project.averageScore { row("Score moyen", String(format: "%.1f", avg), color: Theme.scoreColor(avg)) }
            if let r = project.resolution { row("Résolution", "\(r.shortLabel) · \(r.label)") }
            if let fps = project.fps { row("Images/s", String(format: "%.0f", fps)) }
            if let a = project.audioTracks { row("Pistes audio", "\(a)") }
            if let f = project.sourceFilename { row("Fichier", f) }
            if let rel = project.relativeCreated { row("Créé", rel) }
            if let err = project.errorMessage, !err.isEmpty { row("Erreur", err, color: Theme.danger) }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 14)
        .forgeGlassCard(cornerRadius: 18)
    }

    private func row(_ label: String, _ value: String, color: Color = Theme.textPrimary) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label).font(.subheadline).foregroundStyle(Theme.textSecondary)
            Spacer(minLength: 12)
            Text(value)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(color)
                .multilineTextAlignment(.trailing)
                .lineLimit(2)
        }
        .padding(.vertical, 10)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Theme.textSecondary.opacity(0.10)).frame(height: 0.5)
        }
    }

    private func sourceLink(_ url: URL, raw: String) -> some View {
        Link(destination: url) {
            HStack(spacing: 10) {
                Image(systemName: "link").foregroundStyle(Theme.accent)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Source").font(.caption).foregroundStyle(Theme.textSecondary)
                    Text(raw).font(.subheadline).foregroundStyle(Theme.textPrimary).lineLimit(1)
                }
                Spacer()
                Image(systemName: "arrow.up.right.square").foregroundStyle(Theme.textSecondary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .forgeGlassCard(cornerRadius: 16)
        }
        .buttonStyle(.plain)
    }

    // MARK: Jobs

    @ViewBuilder
    private var jobsSection: some View {
        if !jobs.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Text("Jobs récents").font(.headline).foregroundStyle(Theme.textPrimary)
                ForEach(jobs) { job in jobRow(job) }
            }
        } else if jobsLoaded && !demo {
            EmptyView()
        }
    }

    private func jobRow(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(job.typeLabel).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.textPrimary)
                Spacer()
                Text(job.statusLabel)
                    .font(.caption2.weight(.semibold)).foregroundStyle(.white)
                    .padding(.horizontal, 7).padding(.vertical, 2)
                    .background(job.statusColor).clipShape(Capsule())
            }
            if job.isActive {
                ProgressView(value: job.fraction).tint(Theme.accent)
                if let stage = job.stage, !stage.isEmpty {
                    Text(stage).font(.caption).foregroundStyle(Theme.textSecondary)
                }
            } else if let err = job.error, !err.isEmpty {
                Text(err).font(.caption).foregroundStyle(Theme.danger).lineLimit(2)
            }
        }
        .padding(14)
        .forgeGlassCard(cornerRadius: 16)
    }

    private func loadJobs() async {
        guard !demo else {
            jobs = []
            jobsLoaded = true
            return
        }
        defer { jobsLoaded = true }
        if let result = try? await api.fetchJobs(projectId: project.id) {
            // Most recent first; cap the list so detail stays glanceable.
            jobs = Array(result.reversed().prefix(8))
        }
    }
}
