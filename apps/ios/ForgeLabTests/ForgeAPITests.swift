import XCTest
@testable import ForgeLab

/// Network-free tests for ForgeAPI. We register a URLProtocol that resolves
/// every request from an in-memory stub table; no real HTTP traffic, no
/// timing flakes.
final class ForgeAPITests: XCTestCase {

    var api: ForgeAPI!

    override func setUp() {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let session = URLSession(configuration: config)
        api = ForgeAPI(
            baseURL: URL(string: "http://10.0.0.1:8420")!,
            apiKey: "forge_secret",
            session: session,
        )
        StubURLProtocol.reset()
    }

    func testClipsByDateDecoded() async throws {
        StubURLProtocol.stub(
            method: "GET",
            pathContains: "/v1/clips/by-date",
            status: 200,
            json: """
            {
              "date": "2026-06-13",
              "count": 1,
              "items": [{
                "id": "abc",
                "projectId": "p",
                "segmentId": "s",
                "title": "Hook",
                "description": "yo",
                "hashtags": ["viral"],
                "coverPath": null,
                "duration": 30.5,
                "viralScore": 82.0,
                "status": "pending_review",
                "channelName": "etostark__",
                "createdAt": "2026-06-13T01:00:00"
              }]
            }
            """,
        )
        let day = ISO8601DateFormatter().date(from: "2026-06-13T00:00:00Z")!
        let resp = try await api.clipsByDate(day)
        XCTAssertEqual(resp.count, 1)
        XCTAssertEqual(resp.items.first?.title, "Hook")
        XCTAssertEqual(resp.items.first?.viralScore, 82.0)
    }

    func testHeadersIncludeApiKey() async throws {
        StubURLProtocol.stub(method: "GET", pathContains: "/v1/clips/queue/summary",
                             status: 200, json: #"{"counts": {}, "total": 0}"#)
        _ = try await api.queueSummary()
        let captured = try XCTUnwrap(StubURLProtocol.lastRequest)
        XCTAssertEqual(captured.value(forHTTPHeaderField: "X-API-Key"), "forge_secret")
    }

    func testUnauthorizedSurfaces() async {
        StubURLProtocol.stub(method: "GET", pathContains: "/v1/clips/by-date",
                             status: 401, json: #"{"detail": "nope"}"#)
        let day = Date()
        do {
            _ = try await api.clipsByDate(day)
            XCTFail("expected throw")
        } catch let error as ApiError {
            XCTAssertEqual(error, .unauthorized)
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func testRateLimitSurfacesRetryAfter() async {
        StubURLProtocol.stub(method: "GET", pathContains: "/v1/clips/queue/summary",
                             status: 429,
                             json: #"{"detail": "Rate limit exceeded"}"#,
                             headers: ["Retry-After": "7"])
        do {
            _ = try await api.queueSummary()
            XCTFail("expected throw")
        } catch let error as ApiError {
            XCTAssertEqual(error, .rateLimited(retryAfter: 7))
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func testBatchApproveBodySerialization() async throws {
        StubURLProtocol.stub(
            method: "POST",
            pathContains: "/v1/clips/batch-approve",
            status: 200,
            json: #"{"requested": 2, "approved": 2, "skipped": []}"#,
        )
        let resp = try await api.batchApprove(ids: ["a", "b"])
        XCTAssertEqual(resp.approved, 2)
        let bodyData = try XCTUnwrap(StubURLProtocol.lastRequest?.httpBody
                                 ?? StubURLProtocol.lastBodyFromStream)
        let obj = try JSONSerialization.jsonObject(with: bodyData) as? [String: Any]
        XCTAssertEqual(obj?["ids"] as? [String], ["a", "b"])
    }

    func testServerErrorIncludesDetail() async {
        StubURLProtocol.stub(method: "GET", pathContains: "/v1/clips/queue/summary",
                             status: 500, json: #"{"detail": "boom"}"#)
        do {
            _ = try await api.queueSummary()
            XCTFail("expected throw")
        } catch let error as ApiError {
            if case .server(let status, let detail) = error {
                XCTAssertEqual(status, 500)
                XCTAssertEqual(detail, "boom")
            } else { XCTFail("wrong case: \(error)") }
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }
}

// MARK: - Network stub

final class StubURLProtocol: URLProtocol {
    struct Stub {
        let method: String
        let pathContains: String
        let status: Int
        let body: Data
        let headers: [String: String]
    }
    nonisolated(unsafe) static var stubs: [Stub] = []
    nonisolated(unsafe) static var lastRequest: URLRequest?
    nonisolated(unsafe) static var lastBodyFromStream: Data?

    static func reset() {
        stubs.removeAll()
        lastRequest = nil
        lastBodyFromStream = nil
    }

    static func stub(method: String, pathContains: String, status: Int,
                     json: String, headers: [String: String] = [:]) {
        stubs.append(.init(method: method, pathContains: pathContains, status: status,
                           body: json.data(using: .utf8) ?? Data(), headers: headers))
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lastRequest = request
        if let stream = request.httpBodyStream {
            Self.lastBodyFromStream = Self.readStream(stream)
        }
        let path = request.url?.path ?? ""
        let method = request.httpMethod ?? "GET"
        let match = Self.stubs.first { stub in
            stub.method == method && path.contains(stub.pathContains)
        }
        guard let match else {
            let err = NSError(domain: "stub", code: 404)
            client?.urlProtocol(self, didFailWithError: err)
            return
        }
        var headers = match.headers
        headers["Content-Type"] = "application/json"
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: match.status,
            httpVersion: "HTTP/1.1",
            headerFields: headers,
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: match.body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private static func readStream(_ stream: InputStream) -> Data {
        stream.open(); defer { stream.close() }
        var data = Data()
        let bufferSize = 4096
        let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        defer { buffer.deallocate() }
        while stream.hasBytesAvailable {
            let read = stream.read(buffer, maxLength: bufferSize)
            if read <= 0 { break }
            data.append(buffer, count: read)
        }
        return data
    }
}
