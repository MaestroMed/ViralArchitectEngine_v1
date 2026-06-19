import Foundation

// Mirrors /v1/analytics/* (NOT enveloped — the handlers return the object
// directly). View/engagement figures are 0 until an external publisher records
// them; the meaningful data today is clip production + viral-score ranking.

struct AnalyticsOverview: Decodable, Sendable, Hashable {
    let totalClips: Int
    let pendingReview: Int
    let approved: Int
    let published: Int
    let rejected: Int
    let scheduled: Int
    let clipsLast7Days: Int
    let avgViralScore: Double
    let topViralScore: Double
    let totalViews: Int
    let totalEngagement: Int
}

struct TopClip: Identifiable, Decodable, Sendable, Hashable {
    let clipId: String
    let projectId: String?
    let segmentId: String?
    let title: String?
    let viralScore: Double
    let status: String
    let channelName: String?
    let duration: Double
    let createdAt: String?
    let views: Int

    var id: String { clipId }

    var durationLabel: String {
        let t = Int(duration.rounded())
        return String(format: "%d:%02d", t / 60, t % 60)
    }
}

struct TrendPoint: Identifiable, Decodable, Sendable, Hashable {
    let date: String       // yyyy-MM-dd
    let clips: Int
    let views: Int
    var id: String { date }

    /// "16/06" short label for the axis.
    var shortLabel: String {
        let parts = date.split(separator: "-")
        return parts.count == 3 ? "\(parts[2])/\(parts[1])" : date
    }
}

struct AnalyticsTrends: Decodable, Sendable, Hashable {
    let granularity: String
    let periodDays: Int
    let points: [TrendPoint]
}

/// `GET /v1/analytics/dashboard` — the one call the Stats tab uses.
struct AnalyticsDashboard: Decodable, Sendable {
    let overview: AnalyticsOverview
    let topClips: [TopClip]
    let trends: AnalyticsTrends
}

/// `GET /v1/analytics/top-clips` wraps the list in `{clips, metric, period_days}`.
struct TopClipsResponse: Decodable {
    let clips: [TopClip]
}
