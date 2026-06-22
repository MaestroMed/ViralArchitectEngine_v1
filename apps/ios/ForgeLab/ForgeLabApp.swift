import AVFoundation
import SwiftUI

@main
struct ForgeLabApp: App {
    /// Bridges the UIKit app delegate so we can receive the APNs device token
    /// (that callback is delegate-only). See PushRegistrar / AppDelegate.
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
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
                    // Clip audio must play through the SILENT switch — without the
                    // .playback category AVPlayer mutes video on a silenced phone.
                    try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
                    notifications = NotificationManager(router: router)
                    LocalNotifier.requestAuthorization()
                    // Register for REMOTE push (APNs) on top of local notifs, so
                    // a backgrounded phone wakes on "clips ready". No-op in demo.
                    PushRegistrar.shared.registerForRemoteNotifications()
                }
                // If the engine is configured after a token already arrived,
                // (re)sync it so registration isn't lost to ordering.
                .onChange(of: settings.isConfigured) { _, configured in
                    if configured { Task { await PushRegistrar.shared.syncToEngine() } }
                }
        }
    }
}
