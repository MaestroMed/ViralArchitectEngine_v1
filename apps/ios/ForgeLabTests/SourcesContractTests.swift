import XCTest
@testable import ForgeLab

/// Contract test for the Sources surfaces (channels / detected VODs / video
/// info). Decodes real + representative engine payloads from `Fixtures/`.
final class SourcesContractTests: XCTestCase {

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

    func testChannelsDecode() throws {
        let env = try load(ApiEnvelope<[WatchedChannel]>.self, "channels.sample.json")
        let channels = try XCTUnwrap(env.data)
        let ch = try XCTUnwrap(channels.first)
        XCTAssertEqual(ch.channelId, "etostark")
        XCTAssertEqual(ch.platform, "twitch")
        XCTAssertTrue(ch.enabled)
        XCTAssertEqual(ch.checkInterval, 3600)
        XCTAssertNil(ch.lastCheckAt)              // null in fixture → optional
        XCTAssertEqual(ch.title, "EtoStark")      // displayName ?? channelName
    }

    func testDetectedVodsPageDecodes() throws {
        let env = try load(ApiEnvelope<DetectedVodsPage>.self, "detected_vods.sample.json")
        let page = try XCTUnwrap(env.data)
        XCTAssertEqual(page.total, 2)
        XCTAssertEqual(page.items.count, 2)

        let fresh = try XCTUnwrap(page.items.first { $0.status == "new" })
        XCTAssertEqual(fresh.externalId, "2798116116")
        XCTAssertEqual(fresh.duration, 8280)            // Int seconds
        XCTAssertEqual(fresh.estimatedScore ?? 0, 72.0, accuracy: 0.001)
        XCTAssertFalse(fresh.isImported)
        XCTAssertEqual(fresh.durationLabel, "2h18")

        let imported = try XCTUnwrap(page.items.first { $0.status == "imported" })
        XCTAssertTrue(imported.isImported)
        XCTAssertNil(imported.duration)                 // null → optional
        XCTAssertNil(imported.thumbnailUrl)
        XCTAssertNotNil(imported.projectId)
    }

    func testCheckChannelResultDecodes() throws {
        // Representative POST /v1/channels/{id}/check response.
        let json = """
        {"success":true,"data":{
          "channel":{"id":"c1","channelId":"etostark","channelName":"EtoStark","displayName":"EtoStark","platform":"twitch","profileImageUrl":null,"enabled":true,"checkInterval":3600,"autoImport":false,"lastCheckAt":"2026-06-17T05:00:00.000000","createdAt":"2026-06-10T10:00:00.000000","updatedAt":"2026-06-17T05:00:00.000000"},
          "newVods":[{"id":"v1","externalId":"999","title":"Nouvelle VOD","channelId":"etostark","channelName":"EtoStark","platform":"twitch","url":"https://twitch.tv/videos/999","thumbnailUrl":null,"duration":3600,"publishedAt":null,"viewCount":10,"status":"new","projectId":null,"estimatedScore":null,"detectedAt":"2026-06-17T05:00:00.000000"}],
          "totalVods":7}}
        """.data(using: .utf8)!
        let env = try JSONDecoder().decode(ApiEnvelope<CheckChannelResult>.self, from: json)
        let result = try XCTUnwrap(env.data)
        XCTAssertEqual(result.totalVods, 7)
        XCTAssertEqual(result.newVods.count, 1)
        XCTAssertEqual(result.channel.channelId, "etostark")
    }

    func testImportResultDecodes() throws {
        // POST /v1/channels/vods/{id}/import → {project, jobId}.
        let json = """
        {"success":true,"data":{"project":{"id":"p1","name":"WAITING ROOM","sourcePath":"","sourceFilename":"x.mp4","duration":null,"resolution":null,"fps":null,"audioTracks":1,"status":"downloading","errorMessage":null,"profileId":null,"metadata":{"importUrl":"https://twitch.tv/videos/1","platform":"twitch","channel":"EtoStark","detectedVodId":"v1"},"createdAt":"2026-06-17T05:00:00.000000","updatedAt":"2026-06-17T05:00:00.000000"},"jobId":"job-123"}}
        """.data(using: .utf8)!
        let env = try JSONDecoder().decode(ApiEnvelope<ImportResult>.self, from: json)
        let result = try XCTUnwrap(env.data)
        XCTAssertEqual(result.jobId, "job-123")
        XCTAssertEqual(result.project.status, "downloading")
        XCTAssertEqual(result.project.metadata?.platform, "twitch")
    }

    func testVideoInfoDecodes() throws {
        // POST /v1/projects/url-info → VideoInfo.
        let json = """
        {"id":"2798116116","title":"WAITING ROOM FRANCE-SÉNÉGAL","description":"desc","duration":8280.0,"thumbnailUrl":"https://x/y.jpg","channel":"EtoStark","channelId":"etostark","uploadDate":"20260615","viewCount":24500,"url":"https://twitch.tv/videos/2798116116","platform":"twitch"}
        """.data(using: .utf8)!
        let info = try JSONDecoder().decode(VideoInfo.self, from: json)
        XCTAssertEqual(info.title, "WAITING ROOM FRANCE-SÉNÉGAL")
        XCTAssertEqual(info.platform, "twitch")
        XCTAssertEqual(info.durationLabel, "2h18")
    }

    func testRequestBodiesEncodeSnakeCase() throws {
        // The engine's Pydantic bodies are snake_case (a camelCase body 422s).
        let enc = JSONEncoder()
        enc.outputFormatting = [.sortedKeys]

        let add = AddChannelRequest(channelId: "etostark", channelName: "EtoStark", platform: "twitch",
                                    displayName: "EtoStark", checkInterval: 3600, autoImport: false, enabled: true)
        let addJson = String(data: try enc.encode(add), encoding: .utf8)!
        XCTAssertTrue(addJson.contains("\"channel_id\""))
        XCTAssertTrue(addJson.contains("\"channel_name\""))
        XCTAssertTrue(addJson.contains("\"auto_import\""))
        XCTAssertFalse(addJson.contains("channelId"))

        let imp = ImportUrlRequest(url: "https://twitch.tv/videos/1", quality: "best",
                                   autoIngest: true, autoAnalyze: true, dictionaryName: "etostark")
        let impJson = String(data: try enc.encode(imp), encoding: .utf8)!
        XCTAssertTrue(impJson.contains("\"auto_ingest\""))
        XCTAssertTrue(impJson.contains("\"auto_analyze\""))
        XCTAssertTrue(impJson.contains("\"dictionary_name\""))

        // Partial PATCH must omit nil fields (synthesized encodeIfPresent).
        let patch = UpdateChannelRequest(enabled: false)
        let patchJson = String(data: try enc.encode(patch), encoding: .utf8)!
        XCTAssertEqual(patchJson, "{\"enabled\":false}")
    }
}
