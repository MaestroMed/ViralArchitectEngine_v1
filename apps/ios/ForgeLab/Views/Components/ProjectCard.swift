import SwiftUI

/// A single VOD project in the Pilot library: source thumbnail, name, lifecycle
/// status, and a compact metrics row (segments · avg score · duration · age).
/// Mirrors `ClipCard`'s glass layout so the two feeds feel like one app.
struct ProjectCard: View {
    let project: Project
    let api: ForgeAPI
    /// Demo mode renders a deterministic gradient instead of hitting the engine.
    var demo: Bool = false
    /// Live job for this project from the WS feed (drives the progress overlay).
    var liveJob: Job? = nil
    /// Fresher status from a WS PROJECT_UPDATE, if any (overrides the fetched one).
    var statusOverride: String? = nil

    private var effectiveStatus: String { statusOverride ?? project.status }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            thumbnail
            VStack(alignment: .leading, spacing: 7) {
                Text(project.name)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.textPrimary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                HStack(spacing: 6) {
                    statusPill
                    if let platform = project.platformLabel {
                        chip(platform, system: "dot.radiowaves.up.forward")
                    }
                }
                if let job = liveJob, job.isActive {
                    liveProgress(job)
                } else {
                    metaRow
                }
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .forgeGlassCard(cornerRadius: 18)
    }

    /// Replaces the metrics row with a live progress bar while a job runs.
    private func liveProgress(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            ProgressView(value: job.fraction).tint(Theme.accent)
                .animation(.easeInOut(duration: 0.3), value: job.fraction)
            HStack(spacing: 6) {
                Image(systemName: "bolt.fill").font(.system(size: 9)).foregroundStyle(Theme.accent)
                Text(job.stage?.isEmpty == false ? "\(job.typeLabel) · \(job.stage!)" : job.typeLabel)
                    .font(.caption2).foregroundStyle(Theme.accent).lineLimit(1)
                Spacer(minLength: 0)
                Text("\(Int(job.progress))%").font(.caption2.monospacedDigit()).foregroundStyle(Theme.textSecondary)
            }
        }
    }

    // MARK: Thumbnail (16:9 source frame)

    @ViewBuilder
    private var thumbnail: some View {
        Group {
            if demo {
                demoThumb
            } else {
                RemoteImage(url: api.projectThumbnailURL(projectId: project.id), api: api) {
                    Rectangle().fill(Theme.background)
                        .overlay(Image(systemName: "film").foregroundStyle(Theme.textSecondary))
                }
            }
        }
        .frame(width: 116, height: 66)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(alignment: .bottomTrailing) {
            if let d = project.durationLabel {
                Text(d)
                    .font(.caption2.weight(.semibold).monospacedDigit())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 5).padding(.vertical, 1)
                    .background(.black.opacity(0.55)).clipShape(Capsule())
                    .padding(5)
            }
        }
    }

    private var demoThumb: some View {
        let palettes: [[Color]] = [
            [Color(red: 0.20, green: 0.10, blue: 0.28), Color(red: 0.06, green: 0.03, blue: 0.10)],
            [Color(red: 0.10, green: 0.20, blue: 0.30), Color(red: 0.03, green: 0.07, blue: 0.12)],
            [Color(red: 0.28, green: 0.16, blue: 0.08), Color(red: 0.10, green: 0.06, blue: 0.03)],
        ]
        let idx = abs(project.id.hashValue) % palettes.count
        return LinearGradient(colors: palettes[idx], startPoint: .topLeading, endPoint: .bottomTrailing)
            .overlay(Image(systemName: "film.stack").foregroundStyle(.white.opacity(0.8)).font(.title3))
    }

    // MARK: Status + metrics

    private var statusPill: some View {
        let color = Project.statusColor(effectiveStatus)
        return HStack(spacing: 4) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text(Project.statusLabel(effectiveStatus))
                .font(.caption2.weight(.semibold))
                .foregroundStyle(color)
        }
        .padding(.horizontal, 7).padding(.vertical, 3)
        .background(color.opacity(0.14))
        .clipShape(Capsule())
    }

    private func chip(_ text: String, system: String) -> some View {
        HStack(spacing: 3) {
            Image(systemName: system).font(.system(size: 8))
            Text(text).font(.caption2.weight(.medium))
        }
        .foregroundStyle(Theme.textSecondary)
        .padding(.horizontal, 7).padding(.vertical, 3)
        .background(Theme.textSecondary.opacity(0.12))
        .clipShape(Capsule())
    }

    private var metaRow: some View {
        HStack(spacing: 10) {
            if let n = project.segmentsCount {
                metric("\(n)", "scissors")
            }
            if let s = project.averageScore {
                HStack(spacing: 3) {
                    Circle().fill(Theme.scoreColor(s)).frame(width: 7, height: 7)
                    Text(String(format: "%.0f", s))
                        .font(.caption2.weight(.semibold).monospacedDigit())
                        .foregroundStyle(Theme.textSecondary)
                }
            }
            if let rel = project.relativeCreated {
                Text(rel).font(.caption2).foregroundStyle(Theme.textSecondary.opacity(0.8))
            }
            Spacer(minLength: 0)
        }
    }

    private func metric(_ value: String, _ icon: String) -> some View {
        HStack(spacing: 3) {
            Image(systemName: icon).font(.system(size: 9)).foregroundStyle(Theme.textSecondary)
            Text(value).font(.caption2.monospacedDigit()).foregroundStyle(Theme.textSecondary)
        }
    }
}
