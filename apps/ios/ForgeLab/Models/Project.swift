import Foundation
import SwiftUI

// Mirrors the engine's `Project.to_dict()` (camelCase, zero CodingKeys — same
// rule as Clip.swift). The list endpoint enriches each item with
// `segmentsCount` + `averageScore`; the single-get endpoint omits them, so both
// are optional here. Forward-compatible: unmodeled metadata keys are ignored.

struct Resolution: Codable, Hashable, Sendable {
    let width: Int
    let height: Int
    var label: String { "\(width)×\(height)" }
    /// 1080p / 720p shorthand when the height is a known tier.
    var shortLabel: String {
        switch height {
        case 2160: return "4K"
        case 1440: return "1440p"
        case 1080: return "1080p"
        case 720: return "720p"
        case 480: return "480p"
        default: return "\(height)p"
        }
    }
}

/// The slice of the free-form project metadata dict the app actually reads.
struct ProjectMetadata: Codable, Hashable, Sendable {
    let platform: String?
    let importUrl: String?
    let channel: String?
}

// Note: the engine also emits `proxyPath` / `audioPath` / `thumbnailPath` — but
// those are absolute paths on the *Mac's* filesystem, useless (and misleading)
// to the phone. Thumbnails are fetched via `projectThumbnailURL(projectId:)`
// (an authenticated endpoint), so we deliberately don't model the raw paths.
struct Project: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let name: String
    let sourcePath: String?
    let sourceFilename: String?
    let duration: Double?
    let resolution: Resolution?
    let fps: Double?
    let audioTracks: Int?
    let status: String
    let errorMessage: String?
    let profileId: String?
    let metadata: ProjectMetadata?
    let createdAt: String
    let updatedAt: String?
    let segmentsCount: Int?
    let averageScore: Double?
}

// MARK: - Display helpers

extension Project {
    /// French human label for any lifecycle status string.
    static func statusLabel(_ status: String) -> String {
        switch status {
        case "created": return "Créé"
        case "downloading": return "Téléchargement"
        case "ingesting": return "Ingestion"
        case "ingested": return "Ingéré"
        case "analyzing": return "Analyse"
        case "analyzed": return "Analysé"
        case "ready": return "Prêt"
        case "error": return "Erreur"
        default: return status.capitalized
        }
    }

    static func statusColor(_ status: String) -> Color {
        switch status {
        case "ready", "analyzed": return Theme.success
        case "error": return Theme.danger
        case "created": return Theme.textSecondary
        default: return Theme.accent          // active/in-progress states
        }
    }

    static func isProcessing(_ status: String) -> Bool {
        ["downloading", "ingesting", "analyzing"].contains(status)
    }

    var statusLabel: String { Self.statusLabel(status) }
    var statusColor: Color { Self.statusColor(status) }

    /// True while the engine is actively working the project (pulsing pill).
    var isProcessing: Bool { Self.isProcessing(status) }

    var platformLabel: String? {
        guard let p = metadata?.platform, !p.isEmpty else { return nil }
        return p.capitalized
    }

    /// "2h12" style runtime, or nil when duration is unknown.
    var durationLabel: String? {
        guard let d = duration, d > 0 else { return nil }
        let total = Int(d.rounded())
        let h = total / 3600, m = (total % 3600) / 60
        if h > 0 { return "\(h)h\(String(format: "%02d", m))" }
        return "\(m)min"
    }

    var createdDate: Date? { Self.isoParser.date(from: createdAt) }

    /// "il y a 3h" / "hier" — relative to now, French.
    var relativeCreated: String? {
        guard let d = createdDate else { return nil }
        return Self.relative.localizedString(for: d, relativeTo: Date())
    }

    private static let relative: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.unitsStyle = .short
        return f
    }()

    /// Parses Python `datetime.isoformat()` (naive, optional fractional seconds,
    /// no trailing Z). ISO8601DateFormatter is too strict for the naive form, so
    /// we fall back through a couple of explicit formats.
    static let isoParser = ISOTimestampParser()
}

/// Tiny helper that tries the few timestamp shapes the engine emits
/// (Python `datetime.isoformat()`: naive, optional microseconds, no trailing Z).
struct ISOTimestampParser {
    private let withFractional: DateFormatter
    private let plain: DateFormatter

    init() {
        func make(_ format: String) -> DateFormatter {
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.timeZone = TimeZone(identifier: "UTC")
            f.dateFormat = format
            return f
        }
        withFractional = make("yyyy-MM-dd'T'HH:mm:ss.SSSSSS")
        plain = make("yyyy-MM-dd'T'HH:mm:ss")
    }

    func date(from string: String) -> Date? {
        withFractional.date(from: string)
            ?? plain.date(from: string)
            ?? ISO8601DateFormatter().date(from: string)
    }
}
