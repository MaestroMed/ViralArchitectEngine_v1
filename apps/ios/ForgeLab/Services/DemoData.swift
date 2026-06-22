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

    /// Demo VOD library for the Pilot tab (--demo / previews). Covers the
    /// lifecycle states the status pill renders (analysing in-progress, analysed,
    /// ready) so screenshots show the full range.
    static let projects: [Project] = [
        Project(
            id: "demo-proj-1",
            name: "[Auto] STARK NIGHTTTT EYWAAAAAAAAA",
            sourcePath: "/vods/v2796529250.mp4", sourceFilename: "video_2796529250.mp4",
            duration: 7930, resolution: Resolution(width: 1920, height: 1080), fps: 30,
            audioTracks: 1, status: "analyzed", errorMessage: nil, profileId: nil,
            metadata: ProjectMetadata(platform: "twitch", importUrl: "https://www.twitch.tv/videos/2796529250", channel: "EtoStark"),
            createdAt: "2026-06-15T02:14:00.000000", updatedAt: "2026-06-15T03:01:00.000000",
            segmentsCount: 412, averageScore: 46.8,
        ),
        Project(
            id: "demo-proj-2",
            name: "[Auto] WAITING ROOM FRANCE-SÉNÉGAL",
            sourcePath: "/vods/v2798116116.mp4", sourceFilename: "video_2798116116.mp4",
            duration: 8280, resolution: Resolution(width: 1920, height: 1080), fps: 30,
            audioTracks: 1, status: "analyzing", errorMessage: nil, profileId: nil,
            metadata: ProjectMetadata(platform: "twitch", importUrl: "https://www.twitch.tv/videos/2798116116", channel: "EtoStark"),
            createdAt: "2026-06-15T09:40:00.000000", updatedAt: "2026-06-15T09:58:00.000000",
            segmentsCount: 168, averageScore: 41.2,
        ),
        Project(
            id: "demo-proj-3",
            name: "[Auto] LE RETOUR DU ROI",
            sourcePath: "/vods/v2787065483.mp4", sourceFilename: "video_2787065483.mp4",
            duration: 10033, resolution: Resolution(width: 1920, height: 1080), fps: 30,
            audioTracks: 1, status: "ready", errorMessage: nil, profileId: nil,
            metadata: ProjectMetadata(platform: "twitch", importUrl: "https://www.twitch.tv/videos/2787065483", channel: "EtoStark"),
            createdAt: "2026-06-14T01:10:00.000000", updatedAt: "2026-06-14T02:30:00.000000",
            segmentsCount: 462, averageScore: 45.5,
        ),
    ]

    /// Demo watched channels for the Sources tab.
    static let channels: [WatchedChannel] = [
        WatchedChannel(
            id: "demo-ch-1", channelId: "etostark", channelName: "EtoStark",
            displayName: "EtoStark", platform: "twitch", profileImageUrl: nil,
            enabled: true, checkInterval: 3600, autoImport: false,
            lastCheckAt: "2026-06-15T08:30:00.000000",
            createdAt: "2026-06-10T10:00:00.000000", updatedAt: "2026-06-15T08:30:00.000000",
        ),
    ]

    /// Demo detected VODs (a fresh one + an already-imported one).
    static let vods: [DetectedVOD] = [
        DetectedVOD(
            id: "demo-vod-1", externalId: "2798116116", title: "WAITING ROOM FRANCE-SÉNÉGAL",
            channelId: "etostark", channelName: "EtoStark", platform: "twitch",
            url: "https://www.twitch.tv/videos/2798116116", thumbnailUrl: nil,
            duration: 8280, publishedAt: "2026-06-15T20:00:00.000000", viewCount: 24500,
            status: "new", projectId: nil, estimatedScore: 72, detectedAt: "2026-06-15T22:10:00.000000",
        ),
        DetectedVOD(
            id: "demo-vod-2", externalId: "2796529250", title: "STARK NIGHTTTT EYWAAAAAAAAA",
            channelId: "etostark", channelName: "EtoStark", platform: "twitch",
            url: "https://www.twitch.tv/videos/2796529250", thumbnailUrl: nil,
            duration: 7930, publishedAt: "2026-06-14T21:00:00.000000", viewCount: 31200,
            status: "imported", projectId: "demo-proj-1", estimatedScore: 68, detectedAt: "2026-06-14T23:00:00.000000",
        ),
    ]

    /// Demo analytics dashboard for the Stats tab.
    static let dashboard = AnalyticsDashboard(
        overview: AnalyticsOverview(
            totalClips: 136, pendingReview: 120, approved: 12, published: 4,
            rejected: 0, scheduled: 0, clipsLast7Days: 42,
            avgViralScore: 67.3, topViralScore: 92.0, totalViews: 0, totalEngagement: 0),
        topClips: [
            TopClip(clipId: "demo-1", projectId: "demo-proj-1", segmentId: "s1",
                    title: "\"Le outplay de Cabochard là c'est ILLÉGAL\"",
                    viralScore: 92, status: "pending_review", channelName: "EtoStark",
                    duration: 34, createdAt: "2026-06-16T21:34:56", views: 0),
            TopClip(clipId: "demo-2", projectId: "demo-proj-1", segmentId: "s2",
                    title: "\"Attends attends ATTENDS il va pas faire ça\"",
                    viralScore: 84, status: "approved", channelName: "EtoStark",
                    duration: 28, createdAt: "2026-06-16T21:30:00", views: 0),
            TopClip(clipId: "demo-3", projectId: "demo-proj-1", segmentId: "s3",
                    title: "\"Wesh mais c'est quoi ce clutch de malade\"",
                    viralScore: 79, status: "pending_review", channelName: "EtoStark",
                    duration: 41, createdAt: "2026-06-15T20:05:00", views: 0),
        ],
        trends: AnalyticsTrends(granularity: "day", periodDays: 30, points: [
            TrendPoint(date: "2026-06-13", clips: 18, views: 0),
            TrendPoint(date: "2026-06-14", clips: 32, views: 0),
            TrendPoint(date: "2026-06-15", clips: 44, views: 0),
            TrendPoint(date: "2026-06-16", clips: 42, views: 0),
        ]))

    /// Demo segment with a real-shaped score breakdown (the "pourquoi" card).
    static let segment = Segment(
        id: "demo-seg",
        score: SegmentScore(
            total: 92, hookStrength: 25, payoff: 12, humourReaction: 18,
            tensionSurprise: 14, clarityAutonomy: 15, rhythm: 8,
            reasons: ["Hook: french_reaction", "Combo bonus: strong hook + humour"],
            tags: ["rage", "outplay", "clutch", "hype"]),
        hookText: "Le outplay de Cabochard là c'est ILLÉGAL",
        topicLabel: "KC vs G2 — la diff top",
        transcript: "Le outplay de Cabochard là c'est ILLÉGAL frère, regarde, regarde ce qu'il fait ! Non mais attends, il a juke les trois en même temps, c'est pas possible. KC vs G2, la diff top qui fait basculer toute la game, c'est de la folie.")

    /// Demo caption-style presets for the Clip Editor (--demo / previews), so
    /// the carousel renders without hitting the engine. Mirrors the engine's
    /// `/v1/clips/caption-presets` ids: classic/hormozi/pop/minimal/neon.
    static let captionPresets: [CaptionPreset] = [
        CaptionPreset(id: "classic", label: "Classic", highlight: "#FFFFFF", pop: false),
        CaptionPreset(id: "hormozi", label: "Hormozi", highlight: "#00FF66", pop: true),
        CaptionPreset(id: "pop", label: "Pop", highlight: "#FFD23F", pop: true),
        CaptionPreset(id: "minimal", label: "Minimal", highlight: "#C9D1D9", pop: false),
        CaptionPreset(id: "neon", label: "Neon", highlight: "#33D9F2", pop: true),
    ]

    /// Demo in-flight job (drives the Pilot live overlay + Jobs sheet).
    static let jobs: [Job] = [
        Job(
            id: "demo-job-1", type: "analyze", projectId: "demo-proj-2", status: "running",
            progress: 62, stage: "transcription", message: "Transcription en cours", error: nil,
            createdAt: "2026-06-15T09:40:00.000000", startedAt: "2026-06-15T09:41:00.000000", completedAt: nil,
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
    /// Defaults to "home" — the dashboard is the real app's landing screen.
    static var demoScreen: String {
        let args = ProcessInfo.processInfo.arguments
        if let i = args.firstIndex(of: "--demo-screen"), i + 1 < args.count {
            return args[i + 1]
        }
        return "home"
    }
}
