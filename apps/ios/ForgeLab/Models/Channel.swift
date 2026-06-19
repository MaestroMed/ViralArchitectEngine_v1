import Foundation

// Sources tab models. Responses are camelCase (channel/VOD `to_dict()`), but the
// engine's POST/PATCH *request* bodies are snake_case Pydantic models — so the
// request structs below map via CodingKeys. (Verified: a camelCase body 422s.)

// MARK: - Responses

struct WatchedChannel: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let channelId: String
    let channelName: String
    let displayName: String?
    let platform: String              // twitch | youtube
    let profileImageUrl: String?
    let enabled: Bool
    let checkInterval: Int            // seconds
    let autoImport: Bool
    let lastCheckAt: String?
    let createdAt: String
    let updatedAt: String?

    var title: String { displayName ?? channelName }

    var lastCheckRelative: String? {
        guard let s = lastCheckAt, let d = Project.isoParser.date(from: s) else { return nil }
        return Self.relative.localizedString(for: d, relativeTo: Date())
    }

    private static let relative: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.unitsStyle = .short
        return f
    }()
}

struct DetectedVOD: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let externalId: String
    let title: String
    let channelId: String
    let channelName: String
    let platform: String
    let url: String
    let thumbnailUrl: String?
    let duration: Int?                 // seconds (DetectedVOD stores an Int)
    let publishedAt: String?
    let viewCount: Int?
    let status: String                // new | imported | ignored
    let projectId: String?
    let estimatedScore: Double?
    let detectedAt: String

    var isImported: Bool { status == "imported" }
    var isIgnored: Bool { status == "ignored" }

    var durationLabel: String? {
        guard let d = duration, d > 0 else { return nil }
        let h = d / 3600, m = (d % 3600) / 60
        if h > 0 { return "\(h)h\(String(format: "%02d", m))" }
        return "\(m)min"
    }

    var viewsLabel: String? {
        guard let v = viewCount, v > 0 else { return nil }
        if v >= 1000 { return String(format: "%.1fk vues", Double(v) / 1000) }
        return "\(v) vues"
    }
}

/// Video metadata for the URL-import preview (`/v1/projects/url-info`).
struct VideoInfo: Codable, Hashable, Sendable {
    let id: String?
    let title: String
    let description: String?
    let duration: Double?
    let thumbnailUrl: String?
    let channel: String?
    let channelId: String?
    let uploadDate: String?
    let viewCount: Int?
    let url: String?
    let platform: String?

    var durationLabel: String? {
        guard let d = duration, d > 0 else { return nil }
        let t = Int(d.rounded()), h = t / 3600, m = (t % 3600) / 60
        if h > 0 { return "\(h)h\(String(format: "%02d", m))" }
        return "\(m)min"
    }
}

// MARK: - Composite response payloads

/// `POST /v1/channels/{id}/check` → updated channel + freshly-detected VODs.
struct CheckChannelResult: Decodable, Sendable {
    let channel: WatchedChannel
    let newVods: [DetectedVOD]
    let totalVods: Int
}

/// `GET /v1/channels/vods/detected` — note: NO `hasMore` (unlike `Paginated`).
struct DetectedVodsPage: Decodable, Sendable {
    let items: [DetectedVOD]
    let total: Int
    let page: Int
    let pageSize: Int
}

/// `POST /v1/channels/vods/{id}/import` → new project + the download/ingest job.
struct ImportResult: Decodable, Sendable {
    let project: Project
    let jobId: String
}

/// `POST /v1/projects/import-url` → project + job + the resolved video metadata.
struct ImportUrlResult: Decodable, Sendable {
    let project: Project
    let jobId: String
    let videoInfo: VideoInfo?
}

// MARK: - Request bodies (snake_case via CodingKeys)

struct AddChannelRequest: Encodable {
    let channelId: String
    let channelName: String
    let platform: String
    let displayName: String?
    let checkInterval: Int
    let autoImport: Bool
    let enabled: Bool

    enum CodingKeys: String, CodingKey {
        case channelId = "channel_id"
        case channelName = "channel_name"
        case platform
        case displayName = "display_name"
        case checkInterval = "check_interval"
        case autoImport = "auto_import"
        case enabled
    }
}

/// Partial PATCH — only non-nil fields are sent (synthesized `encodeIfPresent`).
struct UpdateChannelRequest: Encodable {
    var displayName: String? = nil
    var checkInterval: Int? = nil
    var autoImport: Bool? = nil
    var enabled: Bool? = nil

    enum CodingKeys: String, CodingKey {
        case displayName = "display_name"
        case checkInterval = "check_interval"
        case autoImport = "auto_import"
        case enabled
    }
}

struct UpdateVodStatusRequest: Encodable {
    let status: String   // new | imported | ignored
}

struct ImportUrlRequest: Encodable {
    let url: String
    let quality: String
    let autoIngest: Bool
    let autoAnalyze: Bool
    let dictionaryName: String?

    enum CodingKeys: String, CodingKey {
        case url, quality
        case autoIngest = "auto_ingest"
        case autoAnalyze = "auto_analyze"
        case dictionaryName = "dictionary_name"
    }
}
