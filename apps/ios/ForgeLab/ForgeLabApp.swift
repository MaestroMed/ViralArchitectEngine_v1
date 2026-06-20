import SwiftUI

@main
struct ForgeLabApp: App {
    @StateObject private var settings = Settings.shared
    @StateObject private var router = DeepLinkRouter()
    /// Retained for the lifetime of the app: it owns the UN delegate.
    @State private var notifications: NotificationManager?

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(settings)
                .environmentObject(router)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
                .onOpenURL { router.handle($0) }
                .task {
                    guard notifications == nil else { return }
                    notifications = NotificationManager(router: router)
                    LocalNotifier.requestAuthorization()
                }
        }
    }
}
