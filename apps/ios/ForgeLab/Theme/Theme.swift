import SwiftUI

enum Theme {
    // Deep blue-black so the vivid-blue accent sings against it.
    static let background = Color(red: 0.04, green: 0.05, blue: 0.09)
    static let surface = Color(red: 0.09, green: 0.11, blue: 0.16)

    // Vivid electric blue + its gradient partners (cyan / blue-violet).
    static let accent = Color(red: 0.27, green: 0.56, blue: 1.0)        // #448FFF
    static let accentBright = Color(red: 0.20, green: 0.85, blue: 0.95) // #33D9F2 cyan
    static let accentDeep = Color(red: 0.45, green: 0.40, blue: 1.0)    // #736AFF blue-violet
    static let accentSoft = Color(red: 0.27, green: 0.56, blue: 1.0).opacity(0.18)

    static let textPrimary = Color.white
    // 0.68 (was 0.58): lifts small secondary text to AA contrast on `background`.
    static let textSecondary = Color.white.opacity(0.68)
    static let success = Color(red: 0.25, green: 0.86, blue: 0.58)
    static let danger = Color(red: 0.98, green: 0.36, blue: 0.46)

    /// Shared corner-radius scale so spacing rhythm doesn't drift per view.
    /// (chip → control → card → hero.)
    enum Radius {
        static let sm: CGFloat = 12
        static let md: CGFloat = 16
        static let lg: CGFloat = 20
        static let card: CGFloat = 24
        static let hero: CGFloat = 30
    }

    // MARK: Signature gradients

    /// Primary action gradient — blue → cyan. Buttons, badges, progress.
    static let accentGradient = LinearGradient(
        colors: [accent, accentBright],
        startPoint: .topLeading, endPoint: .bottomTrailing,
    )

    /// Hero gradient — violet → blue → cyan. The "wow" surfaces.
    static let heroGradient = LinearGradient(
        colors: [accentDeep, accent, accentBright],
        startPoint: .topLeading, endPoint: .bottomTrailing,
    )

    /// A soft radial glow used behind hero content.
    static let glowGradient = RadialGradient(
        colors: [accent.opacity(0.45), .clear],
        center: .topTrailing, startRadius: 8, endRadius: 320,
    )

    // Cool score ramp — brighter/greener = better, no warm tones. Weak clips
    // recede (slate), strong ones pop (cyan-green). Mehdi: "j'aime pas le orange".
    static let scoreMid = Color(red: 0.42, green: 0.46, blue: 0.82)   // indigo = "correct"
    static let scoreLow = Color(red: 0.52, green: 0.56, blue: 0.64)   // slate = "faible"

    static func scoreColor(_ score: Double) -> Color {
        switch score {
        case ..<55: return scoreLow                                      // slate = "faible"
        case 55..<70: return scoreMid                                    // indigo = "correct"
        case 70..<85: return accent                                      // blue = "fort"
        default: return success                                          // green = "banger"
        }
    }

    /// Gradient for a score badge — the cooler/greener, the stronger the clip.
    static func scoreGradient(_ score: Double) -> LinearGradient {
        if score >= 85 {
            return LinearGradient(colors: [success, accentBright], startPoint: .topLeading, endPoint: .bottomTrailing)
        }
        if score >= 70 {
            return accentGradient
        }
        if score >= 55 {
            return LinearGradient(colors: [scoreMid, accent], startPoint: .topLeading, endPoint: .bottomTrailing)
        }
        return LinearGradient(colors: [scoreLow, scoreMid], startPoint: .top, endPoint: .bottom)
    }
}
