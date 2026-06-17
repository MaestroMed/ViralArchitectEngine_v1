import Foundation

// Server-side payloads are camelCase already (see ClipQueue.to_dict() in the
// engine). We mirror that here verbatim so there's zero CodingKeys boilerplate.
// If the engine ever switches to snake_case, only this file needs updating.

struct Clip: Identifiable, Codable, Hashable {
    let id: String
    let projectId: String
    let segmentId: String
    let title: String?
    let description: String?
    let hashtags: [String]
    let coverPath: String?
    let duration: Double
    let viralScore: Double
    let status: String
    let channelName: String?
    let createdAt: String  // ISO-8601 — parsed lazily by views that need a Date

    /// The user-facing single-line caption the app drops onto the clipboard.
    /// Server side, this is precomputed in bundle.zip's metadata.json; before
    /// download we fall back to a local concatenation.
    var fallbackCaption: String {
        var parts: [String] = []
        if let t = title?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty {
            parts.append(t)
        }
        if let d = description?.trimmingCharacters(in: .whitespacesAndNewlines),
           !d.isEmpty, d.lowercased() != (title ?? "").lowercased() {
            parts.append(d)
        }
        if !hashtags.isEmpty {
            parts.append(hashtags.map { $0.hasPrefix("#") ? $0 : "#\($0)" }.joined(separator: " "))
        }
        return parts.joined(separator: "\n\n")
    }
}

struct ClipsByDateResponse: Codable {
    let date: String
    let count: Int
    let items: [Clip]
}

struct BatchApproveRequest: Codable {
    let ids: [String]
}

struct BatchApproveResponse: Codable {
    let requested: Int
    let approved: Int
    let skipped: [String]
}

struct QueueSummaryResponse: Codable {
    let counts: [String: Int]
    let total: Int

    var pendingReview: Int { counts["pending_review"] ?? 0 }
    var approved: Int { counts["approved"] ?? 0 }
    var published: Int { counts["published"] ?? 0 }
}

struct HealthResponse: Codable {
    let status: String
    let version: String
    /// Present on the engine's `/health` (omitted by the trimmed mobile fixture
    /// → optional). Drives the Pilot status header's service dots.
    let services: HealthServices?
}

struct HealthServices: Codable, Hashable {
    let ffmpeg: Bool?
    let whisper: Bool?
    let nvenc: Bool?
    let database: Bool?
}
