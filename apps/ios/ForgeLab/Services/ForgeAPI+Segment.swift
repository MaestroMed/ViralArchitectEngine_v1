import Foundation

extension ForgeAPI {
    /// Full segment incl. the score breakdown + hook + transcript (powers the
    /// "pourquoi ce clip" card on clip detail).
    func fetchSegment(projectId: String, segmentId: String) async throws -> Segment {
        let env = try await request(
            ApiEnvelope<Segment>.self,
            path: "/v1/projects/\(projectId)/segments/\(segmentId)",
        )
        return try env.unwrapped()
    }
}
