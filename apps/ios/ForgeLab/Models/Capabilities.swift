import Foundation

// Mirrors the engine's `/v1/capabilities` payload (NOT enveloped — the body is
// the object directly). We only model the fields the Pilot status header reads;
// every sub-object and field is optional so a future engine addition never
// breaks the decode.

struct Capabilities: Decodable, Sendable {
    struct FFmpeg: Decodable, Sendable {
        let version: String?
        let hasNvenc: Bool?
        let hasLibass: Bool?
    }
    struct Whisper: Decodable, Sendable {
        let available: Bool?
        let currentModel: String?
        let device: String?
        let computeType: String?
        let modelLoaded: Bool?
    }
    struct GPU: Decodable, Sendable {
        let available: Bool?
        let count: Int?
    }
    struct Storage: Decodable, Sendable {
        let libraryPath: String?
        let freeSpace: Int?       // bytes
    }

    let ffmpeg: FFmpeg?
    let whisper: Whisper?
    let gpu: GPU?
    let storage: Storage?
}

extension Capabilities {
    /// "428 Go libres" — human free-space, or nil when unknown.
    var freeSpaceLabel: String? {
        guard let bytes = storage?.freeSpace, bytes > 0 else { return nil }
        let f = ByteCountFormatter()
        f.countStyle = .file
        f.allowedUnits = [.useGB, .useTB]
        return f.string(fromByteCount: Int64(bytes))
    }

    /// Short device descriptor for the Whisper chip, e.g. "Whisper large-v3 · CPU".
    var whisperLabel: String? {
        guard let w = whisper, w.available == true else { return nil }
        var parts = ["Whisper"]
        if let m = w.currentModel { parts.append(m) }
        return parts.joined(separator: " ")
    }
}
