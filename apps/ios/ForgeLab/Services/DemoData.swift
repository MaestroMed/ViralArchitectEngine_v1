import Foundation

/// Canned clips used for two things:
/// 1. SwiftUI #Preview providers (design-time).
/// 2. The `--demo` launch argument, so the CI screenshot job
///    (.github/workflows/ios-preview.yml) can render a populated Queue +
///    Detail without a running engine.
///
/// Kept out of any production code path — only reached when the launch
/// argument is present (see `AppLaunch.isDemo`).
enum DemoData {
    static let clips: [Clip] = [
        Clip(
            id: "demo-1", projectId: "p", segmentId: "s1",
            title: "\"Le outplay de Cabochard là c'est ILLÉGAL\"",
            description: "KC vs G2, la diff top qui fait basculer la game",
            hashtags: ["KCORP", "LEC", "Cabochard", "outplay", "viral"],
            coverPath: nil, duration: 34, viralScore: 92, status: "pending_review",
            channelName: "etostark__", createdAt: "2026-06-13T22:14:00",
        ),
        Clip(
            id: "demo-2", projectId: "p", segmentId: "s2",
            title: "\"Attends attends ATTENDS il va pas faire ça\"",
            description: "Le moment où tout le chat panique en live",
            hashtags: ["clutch", "KCORP", "hype"],
            coverPath: nil, duration: 28, viralScore: 84, status: "pending_review",
            channelName: "etostark__", createdAt: "2026-06-13T21:50:00",
        ),
        Clip(
            id: "demo-3", projectId: "p", segmentId: "s3",
            title: "\"Wesh mais c'est quoi ce clutch de malade\"",
            description: "1v3 retourné, Saken en mode dieu",
            hashtags: ["Saken", "1v3", "insane"],
            coverPath: nil, duration: 41, viralScore: 79, status: "pending_review",
            channelName: "etostark__", createdAt: "2026-06-13T20:05:00",
        ),
        Clip(
            id: "demo-4", projectId: "p", segmentId: "s4",
            title: "\"Jpp je suis mort de rire regardez ça\"",
            description: "Le fail le plus drôle du stream",
            hashtags: ["fail", "mdr", "stream"],
            coverPath: nil, duration: 52, viralScore: 68, status: "approved",
            channelName: "etostark__", createdAt: "2026-06-13T19:30:00",
        ),
    ]
}

/// Single source of truth for launch-time flags.
enum AppLaunch {
    /// True when launched with `--demo` (CI screenshots / local design review).
    static var isDemo: Bool {
        ProcessInfo.processInfo.arguments.contains("--demo")
    }

    /// Which demo screen to show first, via `--demo-screen <name>`.
    static var demoScreen: String {
        let args = ProcessInfo.processInfo.arguments
        if let i = args.firstIndex(of: "--demo-screen"), i + 1 < args.count {
            return args[i + 1]
        }
        return "queue"
    }
}
