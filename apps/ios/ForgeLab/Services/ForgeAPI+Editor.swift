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

    /// Queue a re-render of `clipId`. Every field is optional so the same call
    /// powers a plain restyle, a trim, a custom highlight colour, or any mix:
    ///
    /// - `presetId`           — caption style id (classic/hormozi/…); nil keeps current.
    /// - `highlightColorHex`  — "#RRGGBB" override for the active-word highlight; nil = preset default.
    /// - `trimIn` / `trimOut` — clip-relative seconds; send ONLY when the user moved a handle off the full range.
    ///
    /// Builds the enveloped body `{captionStyle:{presetId?,highlightColor?}, trimIn?, trimOut?}`,
    /// omitting any nil key (and dropping `captionStyle` entirely when empty).
    /// Returns the jobId of the spawned EXPORT job (track it over the WS feed).
    func rerenderClip(
        clipId: String,
        presetId: String?,
        highlightColorHex: String? = nil,
        trimIn: Double? = nil,
        trimOut: Double? = nil,
        editedCaptions: [CaptionLine]? = nil,
    ) async throws -> String {
        let style: RerenderRequest.CaptionStyle?
        if presetId != nil || highlightColorHex != nil {
            style = .init(presetId: presetId, highlightColor: highlightColorHex)
        } else {
            style = nil
        }
        let body = RerenderRequest(
            captionStyle: style, trimIn: trimIn, trimOut: trimOut, editedCaptions: editedCaptions,
        )
        let env = try await request(ApiEnvelope<RerenderResult>.self,
                                    path: "/v1/clips/queue/\(clipId)/rerender",
                                    method: "POST", body: body)
        return try env.unwrapped().jobId
    }

    /// The clip's caption LINES (clip-relative) for the text editor.
    func clipCaptions(clipId: String) async throws -> [CaptionLine] {
        let env = try await request(ApiEnvelope<CaptionLinesPayload>.self,
                                    path: "/v1/clips/queue/\(clipId)/captions")
        return try env.unwrapped().lines
    }
}

/// One editable caption line + its words. Round-trips to the engine verbatim
/// (the engine keeps each word's timing on a same-count text fix).
struct CaptionLine: Codable, Identifiable, Hashable {
    let start: Double
    let end: Double
    var text: String
    let words: [CaptionWord]
    var id: String { "\(start)-\(end)" }
}

struct CaptionWord: Codable, Hashable {
    let word: String
    let start: Double
    let end: Double
}

private struct CaptionLinesPayload: Decodable {
    let lines: [CaptionLine]
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

/// Enveloped re-render body. `Encodable` synthesis already omits `nil`
/// Optionals from the JSON, so the engine only sees the keys the user touched.
private struct RerenderRequest: Encodable {
    let captionStyle: CaptionStyle?
    let trimIn: Double?
    let trimOut: Double?
    let editedCaptions: [CaptionLine]?

    struct CaptionStyle: Encodable {
        let presetId: String?
        let highlightColor: String?   // "#RRGGBB"
    }
}
