import Foundation

/// Every failure surface the UI cares about, normalised. Networking errors
/// (no route to host, timeout) collapse into `.unreachable`; auth-shaped
/// 4xx into `.unauthorized`; anything else with a body into `.server`.
enum ApiError: LocalizedError, Equatable {
    case notConfigured
    case unreachable(underlying: String)
    case unauthorized
    case rateLimited(retryAfter: Int)
    case notFound
    case server(status: Int, detail: String?)
    case decoding(reason: String)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Configure d'abord l'IP du moteur et la clé API dans Réglages."
        case .unreachable(let why):
            return "Moteur injoignable (\(why)). Vérifie que ton PC est sur le même WiFi."
        case .unauthorized:
            return "Clé API rejetée. Crée-en une nouvelle sur le moteur (forge-keys create)."
        case .rateLimited(let retry):
            return "Trop de requêtes — réessaie dans \(retry)s."
        case .notFound:
            return "Introuvable côté moteur."
        case .server(let status, let detail):
            return "Erreur \(status)\(detail.map { ": \($0)" } ?? "")"
        case .decoding(let why):
            return "Réponse inattendue du moteur (\(why))."
        }
    }
}
