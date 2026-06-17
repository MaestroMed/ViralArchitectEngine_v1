import Foundation

// The engine's /v1 JSON routes (projects, jobs, …) wrap their payload in a
// `{success, data, error, message}` envelope — unlike the mobile clip routes,
// which return their body bare (see Clip.swift). Decoding goes through this
// generic so each call site just gets the inner `data`.

struct ApiEnvelope<T: Decodable>: Decodable {
    let success: Bool
    let data: T?
    let error: String?
    let message: String?
}

/// Generic page wrapper used by list endpoints (`/v1/projects`). Mirrors the
/// backend `PaginatedResponseSchema` (camelCase).
struct Paginated<T: Decodable>: Decodable {
    let items: [T]
    let total: Int
    let page: Int
    let pageSize: Int
    let hasMore: Bool
}
