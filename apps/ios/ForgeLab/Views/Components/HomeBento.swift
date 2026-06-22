import SwiftUI

/// Signature element: a living blue mesh that slowly flows. Static under Reduce
/// Motion + in demo/CI (a forever-running TimelineView stalls XCUITest).
struct AnimatedMeshHero: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private var animate: Bool { !reduceMotion && !AppLaunch.isDemo }

    private let colors: [Color] = [
        Theme.accentDeep, Theme.accent, Theme.accentBright,
        Theme.accent, Theme.accentBright, Theme.accentDeep,
        Theme.accentDeep, Theme.accent, Theme.accentBright,
    ]

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 20.0, paused: !animate)) { timeline in
            let p = animate ? CGFloat(timeline.date.timeIntervalSinceReferenceDate) : 0
            MeshGradient(width: 3, height: 3, points: points(p), colors: colors)
        }
        .accessibilityHidden(true)   // purely decorative signature mesh
    }

    private func points(_ p: CGFloat) -> [SIMD2<Float>] {
        func w(_ base: Float, _ amp: Float, _ speed: Float, _ off: Float) -> Float {
            base + amp * Float(sin(Double(p) * Double(speed) + Double(off)))
        }
        return [
            [0, 0], [w(0.5, 0.10, 0.62, 0.0), 0], [1, 0],
            [0, w(0.5, 0.12, 0.50, 1.0)], [w(0.5, 0.14, 0.85, 2.0), w(0.5, 0.12, 0.58, 3.0)], [1, w(0.5, 0.12, 0.43, 4.0)],
            [0, 1], [w(0.5, 0.10, 0.74, 5.0), 1], [1, 1],
        ]
    }
}

/// Signature score visualisation — a gradient ring instead of a flat number.
/// The trim sweeps in on appear (static under Reduce Motion + demo/CI so
/// XCUITest screenshots stay deterministic).
struct ScoreRing: View {
    let score: Double
    var size: CGFloat = 56
    var lineWidth: CGFloat = 5

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var trim: CGFloat = 0

    private var target: CGFloat { max(0.02, min(1, CGFloat(score) / 100)) }

    var body: some View {
        ZStack {
            Circle().stroke(Color.white.opacity(0.14), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: trim)
                .stroke(Theme.scoreGradient(score),
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
            Text("\(Int(score.rounded()))")
                .font(.system(size: size * 0.34, weight: .bold, design: .rounded).monospacedDigit())
                .foregroundStyle(.white)
                .contentTransition(.numericText())
        }
        .frame(width: size, height: size)
        .accessibilityElement(children: .ignore)   // gradient ring is decorative
        .accessibilityLabel("Score \(Int(score.rounded()))")
        .onAppear {
            if reduceMotion || AppLaunch.isDemo {
                trim = target
            } else {
                withAnimation(.spring(response: 0.7, dampingFraction: 0.85)) { trim = target }
            }
        }
    }
}
