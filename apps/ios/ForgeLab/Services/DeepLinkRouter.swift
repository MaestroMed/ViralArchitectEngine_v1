import Foundation

/// Routes `forge-lab://…` deep links (from a notification tap or a future APNs
/// payload) to a tab. Shared via the environment; `MainTabView` reacts to
/// `target` and clears it.
@MainActor
final class DeepLinkRouter: ObservableObject {
    /// The tab to switch to (Accueil 0 / Pilote 1 / Sources 2 / Clips 3 / Stats 4).
    @Published var target: Int?

    func handle(_ url: URL) {
        guard url.scheme == "forge-lab" else { return }
        switch url.host {
        case "clips", "review": target = 3
        case "pilote", "pilot": target = 1
        case "sources": target = 2
        case "stats": target = 4
        case "accueil", "home": target = 0
        default: break
        }
    }

    /// Deep link a notification should carry to land in the review queue.
    static let reviewURL = URL(string: "forge-lab://clips")!
}
