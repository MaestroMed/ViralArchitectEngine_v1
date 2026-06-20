import Foundation
import UserNotifications

/// Schedules local notifications. Today these fire while the app is open (e.g.
/// a job finishes while you're on another tab) — the same payload shape a future
/// APNs server push would use, so the deep-link path is identical.
enum LocalNotifier {
    static func requestAuthorization() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    /// Notify that new clips are ready to review; tapping deep-links to the queue.
    static func clipsReady(message: String = "De nouveaux clips sont prêts à reviewer") {
        let content = UNMutableNotificationContent()
        content.title = "Clips prêts ✨"
        content.body = message
        content.sound = .default
        content.userInfo = ["url": DeepLinkRouter.reviewURL.absoluteString]
        let req = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(req)
    }
}

/// UNUserNotificationCenter delegate: show banners in the foreground and route
/// taps into the `DeepLinkRouter`.
final class NotificationManager: NSObject, UNUserNotificationCenterDelegate {
    private let router: DeepLinkRouter

    init(router: DeepLinkRouter) {
        self.router = router
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
    ) async {
        let urlStr = response.notification.request.content.userInfo["url"] as? String
        await MainActor.run {
            if let urlStr, let url = URL(string: urlStr) { router.handle(url) }
        }
    }
}
