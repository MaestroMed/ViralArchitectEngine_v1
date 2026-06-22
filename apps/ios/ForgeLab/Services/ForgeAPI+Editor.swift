import Foundation

// In-app clip editor surface (MVP): list the engine's dynamic caption-style
// presets, and re-render a clip with a chosen style. The re-render is queued as
// an EXPORT job server-side; the ClipQueue row's video is replaced in place when
// it finishes — so the client tracks the returned jobId over the live WS feed
// and refetches the (now-refreshed) video URL on completion.
//
// Both routes live under the enveloped `/v1` surface (`{success,data,...}`), so
// we decode through `ApiEnvelope` like the Sources/Pilot calls — not bare like
// the older mobile clip routes.
extension ForgeAPI {

    /// The dynamic caption styles the editor offers (ids: classic/hormozi/pop/
    /// minimal/neon). Decoded from `data.presets`.
    func captionPresets() async throws -> [CaptionPreset] {
        let env = try await request(ApiEnvelope<CaptionPresetsPayload>.self,
                                    path: "/v1/clips/caption-presets")
        return try env.unwrapped().presets
    }

    /// Queue a re-render of `clipId` with the given caption preset. Returns the
    /// jobId of the spawned EXPORT job (track it over the WS feed).
    func rerenderClip(clipId: String, presetId: String) async throws -> String {
        let body = RerenderRequest(captionStyle: .init(presetId: presetId))
        let env = try await request(ApiEnvelope<RerenderResult>.self,
                                    path: "/v1/clips/queue/\(clipId)/rerender",
                                    method: "POST", body: body)
        return try env.unwrapped().jobId
    }
}

/// A dynamic caption style the engine can render. `highlight` is a "#RRGGBB"
/// string the UI parses into a tint; `pop` flags styles with a kinetic accent.
struct CaptionPreset: Identifiable, Decodable, Hashable {
    let id: String
    let label: String
    let highlight: String   // "#RRGGBB"
    let pop: Bool
}

// MARK: - Wire shapes (private to the editor surface)

private struct CaptionPresetsPayload: Decodable {
    let presets: [CaptionPreset]
}

private struct RerenderResult: Decodable {
    let jobId: String
    let clipId: String
}

private struct RerenderRequest: Encodable {
    let captionStyle: CaptionStyle
    struct CaptionStyle: Encodable {
        let presetId: String
    }
}
