import Foundation
import Photos
import UIKit

/// One-shot orchestrator: pull the bundle from the engine, drop the .mp4 in
/// the Photos library, copy the caption to the clipboard, then either open
/// TikTok or surface the system share sheet.
///
/// All three side effects (network, photos, pasteboard) need to succeed or
/// fail loudly, but they're independent — we return a `BundleResult` that
/// reports which steps actually completed so the view can show the right
/// success/partial-failure copy.
@MainActor
final class BundleDownloader {
    let api: ForgeAPI

    init(api: ForgeAPI) { self.api = api }

    struct Outcome {
        var savedToPhotos = false
        var captionCopied = false
        var photosError: String?
    }

    func saveToPhotosAndShare(clip: Clip) async throws -> Outcome {
        let zipURL = try await api.downloadBundle(clipId: clip.id)
        defer { try? FileManager.default.removeItem(at: zipURL) }
        let extracted = try Self.extractZip(at: zipURL)
        defer { try? FileManager.default.removeItem(at: extracted.directory) }

        var outcome = Outcome()
        // 1. Photos. Ask for add-only permission so we never need a full library read.
        do {
            try await Self.requestPhotosAddAuthorization()
            try await Self.saveVideo(at: extracted.videoURL)
            outcome.savedToPhotos = true
        } catch {
            outcome.photosError = error.localizedDescription
        }

        // 2. Caption clipboard. Prefer the server-prebuilt caption in
        //    metadata.json (it already joins title + desc + #hashtags
        //    consistently with what we'd compute locally).
        let caption = extracted.caption ?? clip.fallbackCaption
        if !caption.isEmpty {
            UIPasteboard.general.string = caption
            outcome.captionCopied = true
        }

        return outcome
    }

    /// Open TikTok (or the share sheet if it isn't installed). The user finishes
    /// the post manually — pellicule + caption already on the clipboard.
    @discardableResult
    func openTikTokOrShare(from anchor: UIViewController?) -> Bool {
        let tiktok = URL(string: "tiktok://")!
        if UIApplication.shared.canOpenURL(tiktok) {
            UIApplication.shared.open(tiktok)
            return true
        }
        guard let anchor else { return false }
        let activity = UIActivityViewController(activityItems: ["Posté depuis FORGE LAB"], applicationActivities: nil)
        anchor.present(activity, animated: true)
        return false
    }

    // MARK: - Photos plumbing

    private static func requestPhotosAddAuthorization() async throws {
        let status = PHPhotoLibrary.authorizationStatus(for: .addOnly)
        switch status {
        case .authorized, .limited: return
        case .notDetermined:
            let granted = await withCheckedContinuation { c in
                PHPhotoLibrary.requestAuthorization(for: .addOnly) { c.resume(returning: $0) }
            }
            guard granted == .authorized || granted == .limited else {
                throw NSError(domain: "ForgeLab", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "Accès Photos refusé."])
            }
        default:
            throw NSError(domain: "ForgeLab", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Accès Photos refusé. Active-le dans Réglages."])
        }
    }

    private static func saveVideo(at url: URL) async throws {
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            PHPhotoLibrary.shared().performChanges {
                PHAssetCreationRequest.creationRequestForAssetFromVideo(atFileURL: url)
            } completionHandler: { ok, error in
                if ok { c.resume() } else { c.resume(throwing: error ?? NSError(domain: "ForgeLab", code: 2)) }
            }
        }
    }

    // MARK: - Zip extraction
    //
    // iOS 17 ships Apple's `LAContext`-style zip via `Compression` but no
    // public unzip in Foundation. We extract using the same Apple-provided
    // `AppleArchive` framework — no third-party deps.

    struct ExtractedBundle {
        let directory: URL
        let videoURL: URL
        let caption: String?
    }

    static func extractZip(at zipURL: URL) throws -> ExtractedBundle {
        let dest = FileManager.default.temporaryDirectory
            .appendingPathComponent("forgelab-bundle-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dest, withIntermediateDirectories: true)

        // Minimal pure-Foundation zip extractor. We don't deflate aggressively
        // server-side (zipfile compresslevel=1), so we expect stored or
        // lightly-deflated entries. For anything more we'd pull in
        // AppleArchive's libZip; not worth it for the size we ship.
        let entries = try ZipReader.entries(in: zipURL)
        var videoURL: URL?
        var caption: String?
        for entry in entries {
            let out = dest.appendingPathComponent(entry.name)
            try entry.data.write(to: out)
            if entry.name.lowercased().hasSuffix(".mp4") {
                videoURL = out
            }
            if entry.name.lowercased() == "metadata.json" {
                if let dict = try? JSONSerialization.jsonObject(with: entry.data) as? [String: Any] {
                    caption = dict["caption"] as? String
                }
            }
        }
        guard let v = videoURL else {
            throw NSError(domain: "ForgeLab", code: 3,
                          userInfo: [NSLocalizedDescriptionKey: "Bundle sans clip.mp4."])
        }
        return ExtractedBundle(directory: dest, videoURL: v, caption: caption)
    }
}
