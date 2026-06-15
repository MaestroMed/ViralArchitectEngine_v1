import XCTest
@testable import ForgeLab

/// Contract test (iOS side of desktop↔backend↔iOS).
///
/// Decodes the *shared* fixture — `packages/shared/contract/mobile-clip.sample.json`,
/// generated from the real backend `ClipQueue.to_dict()` — into the app's Codable
/// models. If the engine changes the payload shape, this fails, in lock-step with
/// the Python (`test_contract_mobile.py`) and zod (`check-contract.mjs`) suites.
final class MobileContractTests: XCTestCase {

    /// All top-level samples in the fixture, decoded into the iOS models at once.
    /// Unknown keys (`_comment`, `batchApproveRequest`) are ignored by Decodable.
    private struct ContractFixture: Decodable {
        let clip: Clip
        let clipsByDateResponse: ClipsByDateResponse
        let batchApproveResponse: BatchApproveResponse
        let queueSummaryResponse: QueueSummaryResponse
        let health: HealthResponse
    }

    /// Resolve the fixture from the repo tree relative to this source file, so
    /// there is a single source of truth (no copy bundled into the test target).
    private func fixtureURL() throws -> URL {
        var root = URL(fileURLWithPath: #filePath)
        // .../apps/ios/ForgeLabTests/MobileContractTests.swift → repo root
        for _ in 0..<4 { root.deleteLastPathComponent() }
        let url = root
            .appendingPathComponent("packages/shared/contract/mobile-clip.sample.json")
        try XCTSkipUnless(
            FileManager.default.fileExists(atPath: url.path),
            "Contract fixture not found at \(url.path)"
        )
        return url
    }

    func testFixtureDecodesIntoAllModels() throws {
        let data = try Data(contentsOf: try fixtureURL())
        let fixture = try JSONDecoder().decode(ContractFixture.self, from: data)

        // Clip — the morning-workflow fields the UI binds to.
        XCTAssertFalse(fixture.clip.id.isEmpty)
        XCTAssertEqual(fixture.clip.viralScore, 92.0)
        XCTAssertEqual(fixture.clip.status, "pending_review")
        XCTAssertEqual(fixture.clip.channelName, "etostark")
        XCTAssertFalse(fixture.clip.hashtags.isEmpty)

        // by-date envelope
        XCTAssertEqual(fixture.clipsByDateResponse.count,
                       fixture.clipsByDateResponse.items.count)
        XCTAssertEqual(fixture.clipsByDateResponse.items.first?.id, fixture.clip.id)

        // batch-approve + summary + health
        XCTAssertEqual(fixture.batchApproveResponse.requested, 2)
        XCTAssertEqual(fixture.queueSummaryResponse.total, 17)
        XCTAssertEqual(fixture.queueSummaryResponse.pendingReview, 4)
        XCTAssertEqual(fixture.health.status, "healthy")
    }

    func testFallbackCaptionComposesFromFixtureClip() throws {
        let data = try Data(contentsOf: try fixtureURL())
        let fixture = try JSONDecoder().decode(ContractFixture.self, from: data)
        // The caption the app drops onto the clipboard must include the title.
        let caption = fixture.clip.fallbackCaption
        XCTAssertTrue(caption.contains("Cabochard"))
        XCTAssertTrue(caption.contains("#"))
    }
}
