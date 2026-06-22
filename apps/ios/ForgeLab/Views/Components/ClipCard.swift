import SwiftUI

/// A single clip in the queue feed: cover, title, score badge, duration.
/// Selection state is rendered as a coloured ring + check icon overlay.
struct ClipCard: View {
    let clip: Clip
    let api: ForgeAPI
    let selected: Bool
    let selectMode: Bool
    /// Demo mode renders a gradient cover instead of hitting the network, so
    /// CI screenshots look right with no engine. Default false in production.
    var demo: Bool = false

    /// Concise one-sentence summary so VoiceOver reads the card as a unit
    /// instead of 5-7 separate fragments.
    private var a11ySummary: String {
        let name = (clip.title?.isEmpty == false) ? clip.title! : "Clip \(clip.id.prefix(6))"
        var parts = ["\(name), score \(Int(clip.viralScore.rounded())), durée \(formatDuration(clip.duration))"]
        if clip.status != "pending_review" { parts.append(statusLabel(clip.status)) }
        if selectMode { parts.append(selected ? "sélectionné" : "non sélectionné") }
        return parts.joined(separator: ", ")
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            cover
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 6) {
                    if let title = clip.title, !title.isEmpty {
                        Text(title)
                            .font(.headline)
                            .foregroundStyle(Theme.textPrimary)
                            .lineLimit(2)
                    } else {
                        Text("Clip \(clip.id.prefix(6))")
                            .font(.headline)
                            .foregroundStyle(Theme.textSecondary)
                    }
                }
                if let desc = clip.description, !desc.isEmpty {
                    Text(desc)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                        .lineLimit(2)
                }
                HStack(spacing: 8) {
                    ScoreBadge(score: clip.viralScore)
                    Label(formatDuration(clip.duration), systemImage: "clock")
                        .font(.caption2)
                        .foregroundStyle(Theme.textSecondary)
                    if clip.status != "pending_review" {
                        StatusPill(text: statusLabel(clip.status), color: statusColor(clip.status))
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .forgeGlassCard(cornerRadius: 18, selected: selected)
        .overlay(alignment: .topTrailing) {
            if selectMode {
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(selected ? Theme.accent : Theme.textSecondary)
                    .padding(8)
                    .accessibilityHidden(true)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(a11ySummary)
    }

    @ViewBuilder
    private var cover: some View {
        if demo {
            demoCover
        } else {
            networkCover
        }
    }

    /// Deterministic gradient keyed off the clip id — gives each demo card a
    /// distinct cover without any assets.
    private var demoCover: some View {
        let palettes: [[Color]] = [
            [Color(red: 0.11, green: 0.23, blue: 0.42), Color(red: 0.04, green: 0.09, blue: 0.19)],
            [Color(red: 0.14, green: 0.27, blue: 0.20), Color(red: 0.05, green: 0.10, blue: 0.08)],
            [Color(red: 0.10, green: 0.27, blue: 0.30), Color(red: 0.04, green: 0.10, blue: 0.11)],
            [Color(red: 0.14, green: 0.14, blue: 0.34), Color(red: 0.05, green: 0.05, blue: 0.13)],
        ]
        let idx = abs(clip.id.hashValue) % palettes.count
        return LinearGradient(colors: palettes[idx], startPoint: .topLeading, endPoint: .bottomTrailing)
            .overlay(Image(systemName: "play.fill").foregroundStyle(.white.opacity(0.85)).font(.title2))
            .frame(width: 80, height: 142)
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .accessibilityHidden(true)
    }

    private var networkCover: some View {
        RemoteImage(url: api.coverURL(clipId: clip.id), api: api) {
            Rectangle()
                .fill(Theme.background)
                .overlay(Image(systemName: "photo").foregroundStyle(Theme.textSecondary))
        }
        .frame(width: 80, height: 142)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private func formatDuration(_ d: Double) -> String {
        let total = Int(d.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    private func statusLabel(_ s: String) -> String {
        switch s {
        case "approved": return "Approuvé"
        case "rejected": return "Rejeté"
        case "scheduled": return "Programmé"
        case "published": return "Posté"
        case "failed": return "Échec"
        default: return s
        }
    }

    private func statusColor(_ s: String) -> Color {
        switch s {
        case "approved", "scheduled", "published": return Theme.success
        case "rejected", "failed": return Theme.danger
        default: return Theme.textSecondary
        }
    }
}

struct ScoreBadge: View {
    let score: Double
    /// Larger, glowing treatment for hero placements (poster covers, top clips).
    var large: Bool = false

    private var color: Color { Theme.scoreColor(score) }
    private var isHot: Bool { score >= 75 }   // a "winner" — make it pop

    var body: some View {
        Text("\(Int(score.rounded()))")
            .font((large ? Font.subheadline : Font.caption).weight(.bold).monospacedDigit())
            .foregroundStyle(.white)
            .padding(.horizontal, large ? 10 : 8)
            .padding(.vertical, large ? 4 : 3)
            .background(Theme.scoreGradient(score))
            .clipShape(Capsule())
            .shadow(color: isHot ? color.opacity(0.8) : .clear, radius: isHot ? (large ? 9 : 5) : 0)
            .accessibilityElement()
            .accessibilityLabel("Score \(Int(score.rounded()))")
    }
}
