// No Compression import needed: STORED entries are raw bytes from the
// payload section — see extractStored below.

import Foundation

/// Minimal ZIP reader that only handles `ZIP_STORED` entries (no compression).
///
/// The engine writes `bundle.zip` with `zipfile.ZIP_STORED` on purpose: the
/// `.mp4` payload is already compressed, deflate would save fractions of a
/// percent for real CPU cost, and a stored-only reader avoids depending on
/// Compression.framework's raw-deflate quirks. If the producer ever switches
/// back to ZIP_DEFLATED, the reader will throw `.unsupportedCompression` and
/// the failure mode is immediately obvious.
enum ZipReader {
    struct Entry {
        let name: String
        let data: Data
    }

    enum ReaderError: Error, LocalizedError {
        case malformed(String)
        case unsupportedCompression(UInt16)
        var errorDescription: String? {
            switch self {
            case .malformed(let why): return "Archive corrompue: \(why)"
            case .unsupportedCompression(let m):
                return "Méthode de compression non supportée (\(m)). " +
                       "Le moteur doit utiliser ZIP_STORED."
            }
        }
    }

    static func entries(in url: URL) throws -> [Entry] {
        let data = try Data(contentsOf: url, options: .mappedIfSafe)
        return try entries(in: data)
    }

    /// Parses a `Data` buffer directly — handy for unit tests that build
    /// archives in memory.
    static func entries(in data: Data) throws -> [Entry] {
        guard let eocdOffset = findEOCD(in: data) else {
            throw ReaderError.malformed("EOCD not found")
        }
        let entryCount = Int(data.read16(at: eocdOffset + 10))
        let centralDirOffset = Int(data.read32(at: eocdOffset + 16))

        var offset = centralDirOffset
        var entries: [Entry] = []
        for _ in 0..<entryCount {
            guard offset + 46 <= data.count, data.read32(at: offset) == 0x02014b50 else {
                throw ReaderError.malformed("bad central dir signature at \(offset)")
            }
            let method = data.read16(at: offset + 10)
            let compressedSize = Int(data.read32(at: offset + 20))
            let nameLen = Int(data.read16(at: offset + 28))
            let extraLen = Int(data.read16(at: offset + 30))
            let commentLen = Int(data.read16(at: offset + 32))
            let localHeaderOffset = Int(data.read32(at: offset + 42))

            let nameStart = offset + 46
            let nameEnd = nameStart + nameLen
            guard nameEnd <= data.count else {
                throw ReaderError.malformed("name overruns buffer at \(offset)")
            }
            let name = String(data: data.subdata(in: nameStart..<nameEnd), encoding: .utf8) ?? ""

            if !name.hasSuffix("/") {
                let payload = try extractStored(
                    data: data,
                    localOffset: localHeaderOffset,
                    method: method,
                    compressedSize: compressedSize,
                )
                entries.append(Entry(name: name, data: payload))
            }
            offset = nameEnd + extraLen + commentLen
        }
        return entries
    }

    private static func extractStored(
        data: Data,
        localOffset: Int,
        method: UInt16,
        compressedSize: Int,
    ) throws -> Data {
        guard localOffset + 30 <= data.count, data.read32(at: localOffset) == 0x04034b50 else {
            throw ReaderError.malformed("bad local header at \(localOffset)")
        }
        guard method == 0 else { throw ReaderError.unsupportedCompression(method) }
        let nameLen = Int(data.read16(at: localOffset + 26))
        let extraLen = Int(data.read16(at: localOffset + 28))
        let start = localOffset + 30 + nameLen + extraLen
        let end = start + compressedSize
        guard end <= data.count else {
            throw ReaderError.malformed("entry payload overruns buffer")
        }
        return data.subdata(in: start..<end)
    }

    /// EOCD signature 0x06054b50, anywhere in the last 65kB of the file.
    /// Comments after the EOCD are rare in practice and capped at 64kB by spec.
    private static func findEOCD(in data: Data) -> Int? {
        let scanStart = max(0, data.count - 65_557)
        guard data.count >= 22 else { return nil }
        var i = data.count - 22
        while i >= scanStart {
            if data.read32(at: i) == 0x06054b50 { return i }
            i -= 1
        }
        return nil
    }
}

private extension Data {
    func read16(at offset: Int) -> UInt16 {
        return withUnsafeBytes { raw in
            let p = raw.baseAddress!.advanced(by: offset).assumingMemoryBound(to: UInt8.self)
            return UInt16(p[0]) | (UInt16(p[1]) << 8)
        }
    }
    func read32(at offset: Int) -> UInt32 {
        return withUnsafeBytes { raw in
            let p = raw.baseAddress!.advanced(by: offset).assumingMemoryBound(to: UInt8.self)
            return UInt32(p[0]) | (UInt32(p[1]) << 8) | (UInt32(p[2]) << 16) | (UInt32(p[3]) << 24)
        }
    }
}
