import XCTest
@testable import ForgeLab

/// Contract test for the Pilot surfaces (projects / jobs / capabilities).
///
/// Decodes payloads captured from the *real* engine (`Fixtures/*.sample.json`)
/// into the app's Codable models. If the engine changes a project/job/
/// capabilities shape, this fails — the iOS-side half of the desktop↔backend↔iOS
/// lock, alongside `MobileContractTests`.
final class PilotContractTests: XCTestCase {

    /// Resolve a fixture next to this source file (single source of truth, not
    /// bundled into the test target — same approach as MobileContractTests).
    private func fixtureURL(_ name: String) throws -> URL {
        var dir = URL(fileURLWithPath: #filePath)
        dir.deleteLastPathComponent()                       // → ForgeLabTests/
        let url = dir.appendingPathComponent("Fixtures/\(name)")
        try XCTSkipUnless(
            FileManager.default.fileExists(atPath: url.path),
            "Fixture not found at \(url.path)"
        )
        return url
    }

    private func load<T: Decodable>(_ type: T.Type, _ name: String) throws -> T {
        let data = try Data(contentsOf: try fixtureURL(name))
        return try JSONDecoder().decode(T.self, from: data)
    }

    func testProjectsListDecodes() throws {
        let env = try load(ApiEnvelope<Paginated<Project>>.self, "projects.sample.json")
        XCTAssertTrue(env.success)
        let page = try XCTUnwrap(env.data)
        XCTAssertEqual(page.total, 10)
        XCTAssertEqual(page.page, 1)
        XCTAssertEqual(page.items.count, 2)

        let p = try XCTUnwrap(page.items.first)
        XCTAssertEqual(p.status, "analyzed")
        XCTAssertEqual(p.resolution?.width, 1920)
        XCTAssertEqual(p.resolution?.height, 1080)
        XCTAssertEqual(p.segmentsCount, 400)
        XCTAssertEqual(p.averageScore ?? 0, 43.2, accuracy: 0.001)
        XCTAssertEqual(p.metadata?.platform, "twitch")
        XCTAssertEqual(p.metadata?.importUrl, "https://www.twitch.tv/videos/2786253735")
    }

    func testProjectDisplayHelpers() throws {
        let env = try load(ApiEnvelope<Paginated<Project>>.self, "projects.sample.json")
        let p = try XCTUnwrap(env.data?.items.first)
        XCTAssertEqual(p.statusLabel, "Analysé")
        XCTAssertEqual(p.platformLabel, "Twitch")
        XCTAssertEqual(p.resolution?.shortLabel, "1080p")
        // 7929s → 2h12
        XCTAssertEqual(p.durationLabel, "2h12")
        // ISO timestamp (naive, microseconds) must parse.
        XCTAssertNotNil(p.createdDate)
    }

    func testJobsListDecodes() throws {
        let env = try load(ApiEnvelope<[Job]>.self, "jobs.sample.json")
        let jobs = try XCTUnwrap(env.data)
        XCTAssertEqual(jobs.count, 2)

        let running = try XCTUnwrap(jobs.first { $0.status == "running" })
        XCTAssertEqual(running.type, "analyze")
        XCTAssertTrue(running.isActive)
        XCTAssertEqual(running.typeLabel, "Analyse")
        XCTAssertEqual(running.fraction, 0.625, accuracy: 0.001)

        let done = try XCTUnwrap(jobs.first { $0.status == "completed" })
        XCTAssertFalse(done.isActive)
        XCTAssertNotNil(done.completedAt)
    }

    func testCapabilitiesDecodes() throws {
        let caps = try load(Capabilities.self, "capabilities.sample.json")
        XCTAssertEqual(caps.ffmpeg?.hasLibass, true)
        XCTAssertEqual(caps.ffmpeg?.hasNvenc, false)
        XCTAssertEqual(caps.whisper?.currentModel, "large-v3")
        XCTAssertEqual(caps.gpu?.available, false)
        // Free space is a large (>2^31) byte count — must survive as Int64.
        XCTAssertEqual(caps.storage?.freeSpace, 459_318_706_176)
        XCTAssertNotNil(caps.freeSpaceLabel)
        XCTAssertNotNil(caps.whisperLabel)
    }

    func testSegmentScoreBreakdownDecodes() throws {
        let env = try load(ApiEnvelope<Segment>.self, "segment.sample.json")
        let seg = try XCTUnwrap(env.data)
        let score = try XCTUnwrap(seg.score)
        XCTAssertGreaterThan(score.total, 0)
        // The breakdown drives the "pourquoi ce clip" bars.
        XCTAssertFalse(score.components.isEmpty)
        XCTAssertNotNil(seg.hookText)
        // Reasons split into positives + completion caveats.
        XCTAssertEqual(score.positiveReasons.count + score.caveats.count,
                       (score.reasons ?? []).count)
    }

    func testJobStatsEnvelopeDecodes() throws {
        // Inline sample of GET /v1/jobs/stats/summary.
        let json = """
        {"success":true,"data":{"stats":{"pending":1,"running":2,"completed":9,"failed":0,"cancelled":0},"workers":1}}
        """.data(using: .utf8)!
        let env = try JSONDecoder().decode(ApiEnvelope<JobStatsResponse>.self, from: json)
        let stats = try XCTUnwrap(env.data)
        XCTAssertEqual(stats.workers, 1)
        XCTAssertEqual(stats.stats.active, 3)
    }
}
