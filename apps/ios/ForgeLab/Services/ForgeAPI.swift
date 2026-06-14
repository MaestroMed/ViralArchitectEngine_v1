import Foundation

/// Thin typed client around the FORGE Engine HTTP API. All routes are async;
/// every error funnels through `ApiError`.
///
/// Design notes:
/// - `URLSession` is injected so tests can pass a session backed by a custom
///   `URLProtocol` (no real network).
/// - Base URL + API key live in `Settings` but are passed in explicitly here
///   so the type is straightforward to unit-test in isolation.
/// - JSON encoding uses default snake_case-free contracts: the backend's
///   to_dict() already emits camelCase. Bodies we send (BatchApproveRequest)
///   use the same.
struct ForgeAPI: Sendable {
    let baseURL: URL
    let apiKey: String
    let session: URLSession

    init(baseURL: URL, apiKey: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.apiKey = apiKey
        self.session = session
    }

    // MARK: - Public surface

    func ping() async throws {
        // /health is the only unauthenticated route — used by Settings to
        // verify the host before the user even has a key.
        _ = try await request(HealthResponse.self, path: "/health", needsAuth: false)
    }

    func clipsByDate(_ date: Date, channel: String? = nil) async throws -> ClipsByDateResponse {
        var items: [URLQueryItem] = [.init(name: "date", value: Self.isoDay.string(from: date))]
        if let c = channel { items.append(.init(name: "channel", value: c)) }
        return try await request(ClipsByDateResponse.self, path: "/v1/clips/by-date", query: items)
    }

    func queueSummary(channel: String? = nil) async throws -> QueueSummaryResponse {
        let items = channel.map { [URLQueryItem(name: "channel", value: $0)] } ?? []
        return try await request(QueueSummaryResponse.self, path: "/v1/clips/queue/summary", query: items)
    }

    func approve(clipId: String) async throws {
        _ = try await request(EmptyResponse.self, path: "/v1/clips/queue/\(clipId)/approve", method: "POST")
    }

    func reject(clipId: String) async throws {
        _ = try await request(EmptyResponse.self, path: "/v1/clips/queue/\(clipId)/reject", method: "POST")
    }

    func batchApprove(ids: [String]) async throws -> BatchApproveResponse {
        try await request(
            BatchApproveResponse.self,
            path: "/v1/clips/batch-approve",
            method: "POST",
            body: BatchApproveRequest(ids: ids),
        )
    }

    /// URL the AVPlayer scrubs through. Used in `ClipDetailView`.
    func videoURL(clipId: String) -> URL {
        baseURL.appendingPathComponent("/clips/\(clipId)/video")
    }

    /// URL the list view loads thumbnails from. Cover endpoint serves the
    /// generated cover image.
    func coverURL(clipId: String) -> URL {
        baseURL.appendingPathComponent("/v1/clips/\(clipId)/cover")
    }

    /// Download the clip bundle (mp4 + cover + metadata.json) to a temp file.
    /// Returns the local URL; caller is responsible for moving / extracting it.
    func downloadBundle(clipId: String) async throws -> URL {
        var req = URLRequest(url: baseURL.appendingPathComponent("/v1/clips/\(clipId)/bundle.zip"))
        req.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        let (tmp, response) = try await session.download(for: req)
        try Self.expectOK(response)
        // Move out of the URLSession temp dir before it gets reclaimed.
        let dest = FileManager.default.temporaryDirectory
            .appendingPathComponent("forgelab-\(clipId)-\(UUID().uuidString).zip")
        try? FileManager.default.removeItem(at: dest)
        try FileManager.default.moveItem(at: tmp, to: dest)
        return dest
    }

    // MARK: - Helpers

    private struct EmptyResponse: Codable {}

    private static let isoDay: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    func request<T: Decodable>(
        _ type: T.Type,
        path: String,
        method: String = "GET",
        query: [URLQueryItem] = [],
        body: Encodable? = nil,
        needsAuth: Bool = true,
    ) async throws -> T {
        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)
        if !query.isEmpty {
            components?.queryItems = query
        }
        guard let url = components?.url else {
            throw ApiError.notConfigured
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 30
        if needsAuth {
            req.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            do { req.httpBody = try JSONEncoder().encode(AnyEncodable(body)) } catch {
                throw ApiError.decoding(reason: "encode body: \(error.localizedDescription)")
            }
        }

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw ApiError.unreachable(underlying: error.localizedDescription)
        }
        try Self.expectOK(response, payload: data)

        if data.isEmpty, let empty = EmptyResponse() as? T { return empty }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw ApiError.decoding(reason: error.localizedDescription)
        }
    }

    private static func expectOK(_ response: URLResponse, payload: Data = Data()) throws {
        guard let http = response as? HTTPURLResponse else {
            throw ApiError.unreachable(underlying: "non-HTTP response")
        }
        switch http.statusCode {
        case 200...299: return
        case 401, 403: throw ApiError.unauthorized
        case 404: throw ApiError.notFound
        case 429:
            let retry = (http.value(forHTTPHeaderField: "Retry-After")).flatMap(Int.init) ?? 5
            throw ApiError.rateLimited(retryAfter: retry)
        default:
            let detail = String(data: payload, encoding: .utf8)
                .flatMap { extractDetail(json: $0) }
            throw ApiError.server(status: http.statusCode, detail: detail)
        }
    }

    private static func extractDetail(json: String) -> String? {
        // FastAPI returns {"detail": "..."} on errors — pluck it without a
        // full Decodable type so we never explode trying to read a custom body.
        guard let data = json.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return json.prefix(200).trimmingCharacters(in: .whitespacesAndNewlines) }
        return (obj["detail"] as? String) ?? json
    }
}

/// Erase concrete Encodable types so we can keep the API surface generic
/// without forcing every caller to declare its own JSONEncoder.
private struct AnyEncodable: Encodable {
    let wrapped: Encodable
    init(_ wrapped: Encodable) { self.wrapped = wrapped }
    func encode(to encoder: Encoder) throws { try wrapped.encode(to: encoder) }
}
