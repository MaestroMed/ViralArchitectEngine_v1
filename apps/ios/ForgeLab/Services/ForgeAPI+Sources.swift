import Foundation

/// Sources surface: watch channels, check for new VODs, and feed the engine
/// (import a detected VOD or paste a URL). These DO mutate engine state — they
/// kick a download→ingest→analyze pipeline on the Mac — which is the
/// product-decision-gated "trigger compute from the phone" capability (now ON).
extension ForgeAPI {

    // MARK: Channels

    func fetchChannels() async throws -> [WatchedChannel] {
        let env = try await request(ApiEnvelope<[WatchedChannel]>.self, path: "/v1/channels")
        return try env.unwrapped()
    }

    func addChannel(channelId: String, channelName: String, platform: String, displayName: String? = nil) async throws -> WatchedChannel {
        let body = AddChannelRequest(
            channelId: channelId, channelName: channelName, platform: platform,
            displayName: displayName, checkInterval: 3600, autoImport: false, enabled: true,
        )
        let env = try await request(ApiEnvelope<WatchedChannel>.self, path: "/v1/channels", method: "POST", body: body)
        return try env.unwrapped()
    }

    /// Triggers an immediate scrape; returns the channel + any newly-found VODs.
    func checkChannel(id: String) async throws -> CheckChannelResult {
        let env = try await request(ApiEnvelope<CheckChannelResult>.self, path: "/v1/channels/\(id)/check", method: "POST")
        return try env.unwrapped()
    }

    func setChannelEnabled(id: String, enabled: Bool) async throws -> WatchedChannel {
        let env = try await request(
            ApiEnvelope<WatchedChannel>.self, path: "/v1/channels/\(id)",
            method: "PATCH", body: UpdateChannelRequest(enabled: enabled),
        )
        return try env.unwrapped()
    }

    func deleteChannel(id: String) async throws {
        _ = try await request(MessageResponse.self, path: "/v1/channels/\(id)", method: "DELETE")
    }

    // MARK: Detected VODs

    func fetchDetectedVods(status: String? = nil, page: Int = 1, pageSize: Int = 50) async throws -> DetectedVodsPage {
        var q: [URLQueryItem] = [
            .init(name: "page", value: String(page)),
            .init(name: "page_size", value: String(pageSize)),
        ]
        if let status, !status.isEmpty { q.append(.init(name: "status", value: status)) }
        let env = try await request(ApiEnvelope<DetectedVodsPage>.self, path: "/v1/channels/vods/detected", query: q)
        return try env.unwrapped()
    }

    /// Imports a detected VOD → creates a project + kicks download/ingest/analyze.
    func importVod(id: String) async throws -> ImportResult {
        let env = try await request(ApiEnvelope<ImportResult>.self, path: "/v1/channels/vods/\(id)/import", method: "POST")
        return try env.unwrapped()
    }

    func setVodStatus(id: String, status: String) async throws -> DetectedVOD {
        let env = try await request(
            ApiEnvelope<DetectedVOD>.self, path: "/v1/channels/vods/\(id)",
            method: "PATCH", body: UpdateVodStatusRequest(status: status),
        )
        return try env.unwrapped()
    }

    // MARK: URL import

    /// Resolve video metadata without downloading (for the import preview).
    func urlInfo(url: String) async throws -> VideoInfo {
        let body = ImportUrlRequest(url: url, quality: "best", autoIngest: true, autoAnalyze: true, dictionaryName: nil)
        let env = try await request(ApiEnvelope<VideoInfo>.self, path: "/v1/projects/url-info", method: "POST", body: body)
        return try env.unwrapped()
    }

    /// Import from a YouTube/Twitch URL → project + full pipeline job.
    func importUrl(url: String, dictionaryName: String? = "etostark") async throws -> ImportUrlResult {
        let body = ImportUrlRequest(url: url, quality: "best", autoIngest: true, autoAnalyze: true, dictionaryName: dictionaryName)
        let env = try await request(ApiEnvelope<ImportUrlResult>.self, path: "/v1/projects/import-url", method: "POST", body: body)
        return try env.unwrapped()
    }
}
