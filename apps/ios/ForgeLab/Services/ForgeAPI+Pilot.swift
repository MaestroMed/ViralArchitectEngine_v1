import Foundation

/// Read-only Pilot surface: the engine library (projects), job tracking, and
/// hardware capabilities. Every route here is a GET — the phone monitors, it
/// does not trigger compute, publish, or recover (those are Mac-side /
/// product-decision-gated). All calls funnel through `request<T>` so auth and
/// error handling are shared with the rest of `ForgeAPI`.
extension ForgeAPI {

    // MARK: Projects

    func fetchProjects(
        page: Int = 1,
        pageSize: Int = 50,
        search: String? = nil,
        status: String? = nil,
    ) async throws -> Paginated<Project> {
        var q: [URLQueryItem] = [
            .init(name: "page", value: String(page)),
            .init(name: "page_size", value: String(pageSize)),
        ]
        if let search, !search.isEmpty { q.append(.init(name: "search", value: search)) }
        if let status, !status.isEmpty { q.append(.init(name: "status", value: status)) }
        let env = try await request(ApiEnvelope<Paginated<Project>>.self, path: "/v1/projects", query: q)
        return try env.unwrapped()
    }

    func fetchProject(id: String) async throws -> Project {
        let env = try await request(ApiEnvelope<Project>.self, path: "/v1/projects/\(id)")
        return try env.unwrapped()
    }

    // MARK: Jobs

    func fetchJobs(projectId: String? = nil) async throws -> [Job] {
        let q = projectId.map { [URLQueryItem(name: "project_id", value: $0)] } ?? []
        let env = try await request(ApiEnvelope<[Job]>.self, path: "/v1/jobs", query: q)
        return try env.unwrapped()
    }

    func fetchJobStats() async throws -> JobStatsResponse {
        let env = try await request(ApiEnvelope<JobStatsResponse>.self, path: "/v1/jobs/stats/summary")
        return try env.unwrapped()
    }

    /// Cancel a running/pending job. Job control (not a destructive admin route).
    /// Returns `{success, data:{cancelled:true}}`; we only need the HTTP success,
    /// so decode leniently with `MessageResponse` (the `data` key is ignored).
    func cancelJob(id: String) async throws {
        _ = try await request(MessageResponse.self, path: "/v1/jobs/\(id)/cancel", method: "POST")
    }

    // MARK: Capabilities (NOT enveloped — body is the object directly)

    func fetchCapabilities() async throws -> Capabilities {
        try await request(Capabilities.self, path: "/v1/capabilities")
    }

    // MARK: Media

    /// Deterministic URL for a project's source thumbnail (16:9 frame). The
    /// route 401s without the API key, so load it through `RemoteImage`
    /// (which sends the header via `imageData(at:)`), never bare `AsyncImage`.
    func projectThumbnailURL(projectId: String, width: Int = 640, height: Int = 360) -> URL {
        let base = baseURL.appendingPathComponent("/v1/projects/\(projectId)/thumbnail")
        guard var c = URLComponents(url: base, resolvingAgainstBaseURL: false) else { return base }
        c.queryItems = [
            .init(name: "width", value: String(width)),
            .init(name: "height", value: String(height)),
        ]
        return c.url ?? base
    }

    /// Authenticated image fetch. The cover/thumbnail routes require the
    /// `X-API-Key` header, which `AsyncImage` cannot send (so it silently 401s
    /// under LAN auth). `RemoteImage` uses this instead.
    func imageData(at url: URL) async throws -> Data {
        var req = URLRequest(url: url)
        req.timeoutInterval = 30
        req.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw ApiError.unreachable(underlying: error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else {
            throw ApiError.unreachable(underlying: "non-HTTP response")
        }
        switch http.statusCode {
        case 200...299: return data
        case 401, 403: throw ApiError.unauthorized
        case 404: throw ApiError.notFound
        default: throw ApiError.server(status: http.statusCode, detail: nil)
        }
    }

    // MARK: Helpers

    private static func unwrap<T>(_ env: ApiEnvelope<T>) throws -> T {
        // Accept only a genuine success: both the flag AND a payload. An
        // `{success:false, data:…, error:…}` envelope is an error, not data.
        guard env.success, let data = env.data else {
            throw ApiError.server(status: 200, detail: env.error ?? "Réponse vide du moteur")
        }
        return data
    }
}
