import SwiftUI
import UIKit

/// Loads an image from the engine through the *authenticated* session.
///
/// The cover/thumbnail routes return 401 without the `X-API-Key` header, which
/// SwiftUI's `AsyncImage` cannot attach — so under LAN auth those images
/// silently fall back to a placeholder. `RemoteImage` fetches the bytes via
/// `ForgeAPI.imageData(at:)` (header included) and caches the decoded image in
/// memory, so covers actually render and don't re-download on every scroll.
struct RemoteImage<Placeholder: View>: View {
    let url: URL
    let api: ForgeAPI
    var contentMode: ContentMode = .fill
    @ViewBuilder var placeholder: () -> Placeholder

    @State private var image: UIImage?
    @State private var failed = false

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            } else if failed {
                placeholder()
            } else {
                placeholder().overlay(ProgressView())
            }
        }
        .task(id: url) { await load() }
    }

    private func load() async {
        if let cached = RemoteImageCache.shared.image(for: url) {
            image = cached
            return
        }
        do {
            let data = try await api.imageData(at: url)
            if let ui = UIImage(data: data) {
                RemoteImageCache.shared.insert(ui, for: url)
                if !Task.isCancelled { image = ui }
            } else {
                failed = true
            }
        } catch {
            if !Task.isCancelled { failed = true }
        }
    }
}

/// Process-wide in-memory image cache (keyed by full URL). Cheap, bounded, and
/// shared across every `RemoteImage` so the same cover isn't fetched twice.
final class RemoteImageCache {
    static let shared = RemoteImageCache()
    private let cache: NSCache<NSURL, UIImage> = {
        let c = NSCache<NSURL, UIImage>()
        c.countLimit = 200
        return c
    }()

    func image(for url: URL) -> UIImage? { cache.object(forKey: url as NSURL) }
    func insert(_ image: UIImage, for url: URL) { cache.setObject(image, forKey: url as NSURL) }
}
