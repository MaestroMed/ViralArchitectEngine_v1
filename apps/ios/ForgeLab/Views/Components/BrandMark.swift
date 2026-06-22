import SwiftUI

/// Signature brand mark, drawn in code so it stays crisp at any size and always
/// matches the blue theme. Concept: an hourglass funnel — a long VOD pours in
/// through the wide top, gets distilled at the waist, and a short *clip* (the
/// play glyph) drops out the bottom.
struct BrandMark: View {
    var size: CGFloat = 46

    var body: some View {
        Canvas { ctx, sz in
            let w = sz.width, h = sz.height
            func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * w, y: y * h) }

            // Top funnel — wide mouth narrowing to the waist.
            var top = Path()
            top.move(to: pt(0.12, 0.08))
            top.addLine(to: pt(0.88, 0.08))
            top.addLine(to: pt(0.57, 0.44))
            top.addLine(to: pt(0.43, 0.44))
            top.closeSubpath()

            // Waist connector.
            let neck = Path(CGRect(x: 0.43 * w, y: 0.44 * h, width: 0.14 * w, height: 0.06 * h))

            // Bottom triangle (the output clip), pointing up.
            var bottom = Path()
            bottom.move(to: pt(0.5, 0.5))
            bottom.addLine(to: pt(0.9, 0.92))
            bottom.addLine(to: pt(0.1, 0.92))
            bottom.closeSubpath()

            // Play glyph, cut out of the bottom triangle as negative space.
            var play = Path()
            play.move(to: pt(0.44, 0.64))
            play.addLine(to: pt(0.63, 0.77))
            play.addLine(to: pt(0.44, 0.86))
            play.closeSubpath()

            let grad = GraphicsContext.Shading.linearGradient(
                Gradient(colors: [Theme.accentBright, Theme.accent, Theme.accentDeep]),
                startPoint: pt(0.1, 0), endPoint: pt(0.9, 1))

            ctx.fill(top, with: grad)
            ctx.fill(neck, with: grad)
            var clip = bottom
            clip.addPath(play)               // even-odd → play becomes a hole
            ctx.fill(clip, with: grad, style: FillStyle(eoFill: true))
        }
        .frame(width: size, height: size)
        .shadow(color: Theme.accent.opacity(0.35), radius: size * 0.12, y: 1)
        .accessibilityHidden(true)
    }
}
