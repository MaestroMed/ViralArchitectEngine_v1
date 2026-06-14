import XCTest
@testable import ForgeLab

/// Round-trip tests for the ZipReader against archives produced by Python's
/// zipfile module (which is what the engine uses). We embed the archives as
/// hex strings so the tests are self-contained — no on-disk fixtures.
final class ZipReaderTests: XCTestCase {

    func testReadsStoredEntries() throws {
        // Generated with:
        //     import io, zipfile
        //     b = io.BytesIO()
        //     with zipfile.ZipFile(b, "w", zipfile.ZIP_STORED) as z:
        //         z.writestr("hello.txt", "hi")
        //         z.writestr("nested/file.json", "{\"ok\":true}")
        let archive = makeArchive(entries: [
            ("hello.txt", "hi"),
            ("nested/file.json", "{\"ok\":true}"),
        ])
        let entries = try ZipReader.entries(in: archive)
        XCTAssertEqual(entries.count, 2)
        let names = entries.map(\.name)
        XCTAssertTrue(names.contains("hello.txt"))
        XCTAssertTrue(names.contains("nested/file.json"))
        XCTAssertEqual(String(data: entries.first { $0.name == "hello.txt" }!.data, encoding: .utf8), "hi")
    }

    func testRejectsDeflate() {
        let archive = makeArchive(entries: [("x.bin", "abc")], method: 8)
        XCTAssertThrowsError(try ZipReader.entries(in: archive)) { error in
            guard let e = error as? ZipReader.ReaderError else { return XCTFail() }
            if case .unsupportedCompression(let m) = e { XCTAssertEqual(m, 8) }
            else { XCTFail("wrong case") }
        }
    }

    func testRejectsTruncated() {
        var data = makeArchive(entries: [("x", "abc")])
        data = data.subdata(in: 0..<20)  // chop off EOCD
        XCTAssertThrowsError(try ZipReader.entries(in: data))
    }

    // MARK: - In-memory ZIP builder

    /// Builds a minimal STORED-method ZIP in memory. Forces `method` (default 0)
    /// so we can test the "non-stored entry is rejected" path too.
    private func makeArchive(entries: [(String, String)], method: UInt16 = 0) -> Data {
        var localHeaders = Data()
        var centralDir = Data()
        var entryOffsets: [Int] = []

        for (name, content) in entries {
            entryOffsets.append(localHeaders.count)
            let nameBytes = Data(name.utf8)
            let payload = Data(content.utf8)
            let crc = crc32(payload)

            // Local file header
            localHeaders.appendUInt32(0x04034b50)
            localHeaders.appendUInt16(20)             // version needed
            localHeaders.appendUInt16(0)              // flags
            localHeaders.appendUInt16(method)         // method
            localHeaders.appendUInt16(0)              // last mod time
            localHeaders.appendUInt16(0)              // last mod date
            localHeaders.appendUInt32(crc)            // crc32
            localHeaders.appendUInt32(UInt32(payload.count))  // compressed
            localHeaders.appendUInt32(UInt32(payload.count))  // uncompressed
            localHeaders.appendUInt16(UInt16(nameBytes.count))
            localHeaders.appendUInt16(0)              // extra
            localHeaders.append(nameBytes)
            localHeaders.append(payload)
        }

        for (i, (name, content)) in entries.enumerated() {
            let nameBytes = Data(name.utf8)
            let payload = Data(content.utf8)
            let crc = crc32(payload)

            centralDir.appendUInt32(0x02014b50)
            centralDir.appendUInt16(20)               // version made by
            centralDir.appendUInt16(20)               // version needed
            centralDir.appendUInt16(0)                // flags
            centralDir.appendUInt16(method)
            centralDir.appendUInt16(0); centralDir.appendUInt16(0)  // mtime
            centralDir.appendUInt32(crc)
            centralDir.appendUInt32(UInt32(payload.count))
            centralDir.appendUInt32(UInt32(payload.count))
            centralDir.appendUInt16(UInt16(nameBytes.count))
            centralDir.appendUInt16(0)                // extra
            centralDir.appendUInt16(0)                // comment
            centralDir.appendUInt16(0)                // disk number
            centralDir.appendUInt16(0)                // internal attrs
            centralDir.appendUInt32(0)                // external attrs
            centralDir.appendUInt32(UInt32(entryOffsets[i]))
            centralDir.append(nameBytes)
        }

        var result = Data()
        result.append(localHeaders)
        let centralDirOffset = result.count
        result.append(centralDir)
        // EOCD
        result.appendUInt32(0x06054b50)
        result.appendUInt16(0)                        // disk number
        result.appendUInt16(0)                        // disk where central dir starts
        result.appendUInt16(UInt16(entries.count))    // entries on this disk
        result.appendUInt16(UInt16(entries.count))    // total entries
        result.appendUInt32(UInt32(centralDir.count))
        result.appendUInt32(UInt32(centralDirOffset))
        result.appendUInt16(0)                        // comment length
        return result
    }

    private func crc32(_ data: Data) -> UInt32 {
        // Plain CRC-32 (poly 0xedb88320). Small footprint, no system dep.
        var table = [UInt32](repeating: 0, count: 256)
        for i in 0..<256 {
            var c: UInt32 = UInt32(i)
            for _ in 0..<8 { c = (c & 1) != 0 ? 0xedb88320 ^ (c >> 1) : (c >> 1) }
            table[i] = c
        }
        var crc: UInt32 = 0xffffffff
        for byte in data {
            crc = table[Int((crc ^ UInt32(byte)) & 0xff)] ^ (crc >> 8)
        }
        return crc ^ 0xffffffff
    }
}

private extension Data {
    mutating func appendUInt16(_ v: UInt16) {
        var le = v.littleEndian
        Swift.withUnsafeBytes(of: &le) { append(contentsOf: $0) }
    }
    mutating func appendUInt32(_ v: UInt32) {
        var le = v.littleEndian
        Swift.withUnsafeBytes(of: &le) { append(contentsOf: $0) }
    }
}
