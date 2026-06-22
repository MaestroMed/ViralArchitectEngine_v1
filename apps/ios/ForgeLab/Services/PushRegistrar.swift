import SwiftUI
import UIKit
import UserNotifications

/// Owns the remote-push lifecycle on the client:
/// 1. asks `UIApplication` to register for remote notifications (APNs),
/// 2. receives the device token via `AppDelegate` (the UIKit callback that only
///    a `UIApplicationDelegate` can get), and
/// 3. POSTs that token to the engine (`/v1/devices/register`) once the engine
///    URL + key are configured — so a backgrounded phone wakes on "clips ready".
///
/// Local notifications (`LocalNotifier`) remain the in-app fallback; this adds
/// the *remote* path on top, it doesn't replace it.
@MainActor
final class PushRegistrar: ObservableObject {
    static let shared = PushRegistrar()

    /// Latest APNs token (hex), or nil until Apple hands one back.
    @Published private(set) var deviceToken: String?

    /// Last token we successfully registered with the engine — avoids re-POSTing
    /// the identical token to the same host on every foreground.
    private var lastRegisteredToken: String?

    private init() {}

    /// Kick off APNs registration. Safe to call repeatedly (idempotent in UIKit).
    /// Skips entirely in demo/UI-test mode so screenshots never hit the network
    /// or prompt for a (simulator-unsupported) push token.
    func registerForRemoteNotifications() {
        guard !AppLaunch.isDemo else { return }
        // Must be called on the main thread.
        UIApplication.shared.registerForRemoteNotifications()
    }

    /// Called by `AppDelegate` when APNs returns a token.
    func didRegister(deviceToken data: Data) {
        let hex = data.map { String(format: "%02x", $0) }.joined()
        deviceToken = hex
        Task { await self.syncToEngine() }
    }

    func didFailToRegister(error: Error) {
        // Non-fatal: the local-notification fallback still works. The simulator
        // can't issue APNs tokens, so this fires there — expected, not an error
        // worth surfacing to the user.
        #if DEBUG
        print("[Push] registerForRemoteNotifications failed: \(error.localizedDescription)")
        #endif
    }

    /// POST the current token to the engine if we have one and the engine is
    /// configured. Called when a token arrives and whenever settings change.
    func syncToEngine() async {
        guard !AppLaunch.isDemo else { return }
        guard let token = deviceToken else { return }
        let settings = Settings.shared
        guard settings.isConfigured,
              let baseURL = settings.baseURL,
              let key = settings.apiKey, !key.isEmpty
        else { return }
        // Already registered this exact token with the engine? Skip.
        guard token != lastRegisteredToken else { return }

        let api = ForgeAPI(baseURL: baseURL, apiKey: key)
        do {
            try await api.registerDevice(token: token)
            lastRegisteredToken = token
        } catch {
            // Best-effort: a failed registration just means no remote push until
            // the next attempt. Local notifications still fire in-app.
            #if DEBUG
            print("[Push] registerDevice failed: \(error)")
            #endif
        }
    }
}

/// UIKit application delegate adaptor — the ONLY place iOS delivers the APNs
/// device token. SwiftUI's `@UIApplicationDelegateAdaptor` bridges it into the
/// `App` so we keep a pure-SwiftUI lifecycle elsewhere.
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data,
    ) {
        Task { @MainActor in PushRegistrar.shared.didRegister(deviceToken: deviceToken) }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error,
    ) {
        Task { @MainActor in PushRegistrar.shared.didFailToRegister(error: error) }
    }
}
