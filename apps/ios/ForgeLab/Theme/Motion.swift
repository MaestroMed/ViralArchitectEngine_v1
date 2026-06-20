import SwiftUI

// Engine-liveness motion, codified as a small reusable system (not per-screen
// confetti). Every effect is disabled under Reduce Motion AND in demo/CI — a
// forever-repeating animation never settles, which both burns battery and
// stalls XCUITest's idle sync.

extension View {
    /// Gentle pulse (scale + fade) for a "live" indicator — e.g. the active-job
    /// bolt. No-op when `active` is false.
    func forgePulse(active: Bool = true) -> some View {
        modifier(PulseModifier(active: active))
    }

    /// A light sweep across the view — for in-flight progress bars.
    func forgeShimmer(active: Bool = true) -> some View {
        modifier(ShimmerModifier(active: active))
    }
}

private struct PulseModifier: ViewModifier {
    let active: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var animate = false

    private var enabled: Bool { active && !reduceMotion && !AppLaunch.isDemo }

    func body(content: Content) -> some View {
        content
            .scaleEffect(enabled && animate ? 1.35 : 1.0)
            .opacity(enabled && animate ? 0.5 : 1.0)
            .onAppear {
                guard enabled else { return }
                withAnimation(.easeInOut(duration: 0.85).repeatForever(autoreverses: true)) {
                    animate = true
                }
            }
    }
}

private struct ShimmerModifier: ViewModifier {
    let active: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var phase: CGFloat = -1

    private var enabled: Bool { active && !reduceMotion && !AppLaunch.isDemo }

    func body(content: Content) -> some View {
        content.overlay {
            if enabled {
                GeometryReader { geo in
                    LinearGradient(
                        colors: [.clear, .white.opacity(0.35), .clear],
                        startPoint: .leading, endPoint: .trailing,
                    )
                    .frame(width: geo.size.width * 0.55)
                    .offset(x: phase * geo.size.width)
                    .onAppear {
                        withAnimation(.linear(duration: 1.4).repeatForever(autoreverses: false)) {
                            phase = 1.6
                        }
                    }
                }
                .allowsHitTesting(false)
                .clipped()
            }
        }
    }
}
