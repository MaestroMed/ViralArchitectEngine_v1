import Foundation

/// Read-only analytics for the Stats tab. The analytics routes return their
/// payload bare (no {success,data} envelope).
extension ForgeAPI {
    func fetchDashboard(days: Int = 30) async throws -> AnalyticsDashboard {
        try await request(
            AnalyticsDashboard.self, path: "/v1/analytics/dashboard",
            query: [.init(name: "days", value: String(days))],
        )
    }

    func fetchTopClips(limit: Int = 10, metric: String = "score", days: Int = 30) async throws -> [TopClip] {
        let q: [URLQueryItem] = [
            .init(name: "limit", value: String(limit)),
            .init(name: "metric", value: metric),
            .init(name: "days", value: String(days)),
        ]
        return try await request(TopClipsResponse.self, path: "/v1/analytics/top-clips", query: q).clips
    }
}
