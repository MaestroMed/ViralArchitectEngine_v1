import XCTest
@testable import ForgeLab

/// Contract test for the Stats surfaces. Decodes payloads captured from the
/// real engine (after the analytics-500 fix) into the app's Codable models.
final class AnalyticsContractTests: XCTestCase {

    private func fixtureURL(_ name: String) throws -> URL {
        var dir = URL(fileURLWithPath: #filePath)
        dir.deleteLastPathComponent()
        let url = dir.appendingPathComponent("Fixtures/\(name)")
        try XCTSkipUnless(FileManager.default.fileExists(atPath: url.path), "Missing \(url.path)")
        return url
    }

    private func load<T: Decodable>(_ type: T.Type, _ name: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(contentsOf: try fixtureURL(name)))
    }

    func testOverviewDecodes() throws {
        // /v1/analytics/overview returns the object bare (no envelope).
        let o = try load(AnalyticsOverview.self, "analytics_overview.sample.json")
        XCTAssertEqual(o.totalClips, 136)
        XCTAssertEqual(o.avgViralScore, 67.3, accuracy: 0.01)
        XCTAssertGreaterThanOrEqual(o.topViralScore, o.avgViralScore)
        XCTAssertEqual(o.totalViews, 0)          // external metrics not wired yet
    }

    func testDashboardDecodes() throws {
        let d = try load(AnalyticsDashboard.self, "analytics_dashboard.sample.json")
        XCTAssertEqual(d.overview.totalClips, 136)
        XCTAssertFalse(d.topClips.isEmpty)
        XCTAssertFalse(d.trends.points.isEmpty)
        // Top clips are ranked by viral score (descending).
        let scores = d.topClips.map(\.viralScore)
        XCTAssertEqual(scores, scores.sorted(by: >))
        let first = try XCTUnwrap(d.topClips.first)
        XCTAssertEqual(first.channelName, "EtoStark")
        XCTAssertFalse(first.durationLabel.isEmpty)
    }

    func testTopClipsWrapperDecodes() throws {
        // /v1/analytics/top-clips wraps the list in {clips, metric, period_days}.
        let resp = try load(TopClipsResponse.self, "analytics_top_clips.sample.json")
        XCTAssertFalse(resp.clips.isEmpty)
        XCTAssertGreaterThan(try XCTUnwrap(resp.clips.first).viralScore, 0)
    }

    func testTrendPointShortLabel() throws {
        let p = TrendPoint(date: "2026-06-16", clips: 42, views: 0)
        XCTAssertEqual(p.shortLabel, "16/06")
    }
}
