import Foundation
import SwiftUI

// Mirrors the engine's `JobRecord.to_dict()` / `Job.to_dict()` (camelCase).
// Read-only on the phone — the Pilot tab surfaces job progress but never
// triggers, cancels, or recovers (those are Mac-side / decision-gated).

// The engine also emits `result` and `metadata` free-form dicts; the phone
// never reads them, so they're intentionally left off (no AnyCodable churn).
struct Job: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let type: String
    let projectId: String?
    let status: String
    let progress: Double          // 0…100
    let stage: String?
    let message: String?
    let error: String?
    let createdAt: String
    let startedAt: String?
    let completedAt: String?
}

extension Job {
    var isActive: Bool { status == "pending" || status == "running" }

    var statusLabel: String {
        switch status {
        case "pending": return "En file"
        case "running": return "En cours"
        case "completed": return "Terminé"
        case "failed": return "Échec"
        case "cancelled": return "Annulé"
        default: return status.capitalized
        }
    }

    var statusColor: Color {
        switch status {
        case "completed": return Theme.success
        case "failed": return Theme.danger
        case "cancelled": return Theme.textSecondary
        default: return Theme.accent
        }
    }

    var typeLabel: String {
        switch type {
        case "download": return "Téléchargement"
        case "ingest": return "Ingestion"
        case "analyze": return "Analyse"
        case "render_proxy": return "Proxy"
        case "render_final": return "Rendu"
        case "generate_variants": return "Variantes"
        case "export": return "Export"
        default: return type.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    /// Progress as a 0…1 fraction for `ProgressView(value:)`.
    var fraction: Double { max(0, min(1, progress / 100)) }
}

struct JobStats: Decodable, Hashable, Sendable {
    let pending: Int
    let running: Int
    let completed: Int
    let failed: Int
    let cancelled: Int

    /// Jobs the engine is currently working or about to.
    var active: Int { pending + running }
}

struct JobStatsResponse: Decodable, Sendable {
    let stats: JobStats
    let workers: Int
}
