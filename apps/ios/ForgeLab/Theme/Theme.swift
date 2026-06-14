import SwiftUI

enum Theme {
    static let background = Color(red: 0.06, green: 0.07, blue: 0.08)
    static let surface = Color(red: 0.10, green: 0.11, blue: 0.13)
    static let accent = Color(red: 0.95, green: 0.40, blue: 0.20)   // forge orange
    static let accentSoft = Color(red: 0.95, green: 0.40, blue: 0.20).opacity(0.18)
    static let textPrimary = Color.white
    static let textSecondary = Color.white.opacity(0.55)
    static let success = Color(red: 0.30, green: 0.80, blue: 0.45)
    static let danger = Color(red: 0.95, green: 0.30, blue: 0.30)

    static func scoreColor(_ score: Double) -> Color {
        switch score {
        case ..<55: return Color.white.opacity(0.45)
        case 55..<70: return Color(red: 0.95, green: 0.75, blue: 0.30)
        case 70..<85: return accent
        default: return success
        }
    }
}
