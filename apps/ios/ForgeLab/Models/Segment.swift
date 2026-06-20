import Foundation

// The engine already stores a full score *breakdown* per segment (not just the
// single viral number) — this powers the "pourquoi ce clip" card. Camel-case,
// like the rest of the API.

struct SegmentScore: Decodable, Sendable, Hashable {
    let total: Double
    let hookStrength: Double?
    let payoff: Double?
    let humourReaction: Double?
    let tensionSurprise: Double?
    let clarityAutonomy: Double?
    let rhythm: Double?
    let reasons: [String]?
    let tags: [String]?

    /// Present components in display order, labelled in French.
    var components: [Component] {
        var out: [Component] = []
        func add(_ label: String, _ value: Double?) {
            if let value, value > 0 { out.append(Component(label: label, value: value)) }
        }
        add("Accroche", hookStrength)
        add("Humour", humourReaction)
        add("Clarté", clarityAutonomy)
        add("Rythme", rhythm)
        add("Tension", tensionSurprise)
        add("Payoff", payoff)
        return out
    }

    struct Component: Identifiable, Hashable {
        let label: String
        let value: Double
        var id: String { label }
    }

    /// Split the engine's reasons into positives and the one caveat type
    /// ("Too long …", "completion drops").
    var positiveReasons: [String] {
        (reasons ?? []).filter { !$0.lowercased().contains("too long") && !$0.lowercased().contains("drop") }
    }
    var caveats: [String] {
        (reasons ?? []).filter { $0.lowercased().contains("too long") || $0.lowercased().contains("drop") }
    }
}

struct Segment: Decodable, Sendable {
    let id: String
    let score: SegmentScore?
    let hookText: String?
    let topicLabel: String?
    let transcript: String?
}
