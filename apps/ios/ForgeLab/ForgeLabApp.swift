import SwiftUI

@main
struct ForgeLabApp: App {
    @StateObject private var settings = Settings.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(settings)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
    }
}
