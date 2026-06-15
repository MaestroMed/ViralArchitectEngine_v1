import SwiftUI

// FORGE/LAB Liquid Glass design layer (iOS 26).
//
// Reusable glass surfaces so screens share one tactile material instead of the
// old flat `Theme.surface` fills. Wrap clusters of glass views in a
// `GlassEffectContainer` so their shapes blend/merge correctly.

extension View {
    /// Primary card surface — a regular, interactive Liquid Glass layer.
    /// Tints subtly with the forge accent when `selected`.
    @ViewBuilder
    func forgeGlassCard(cornerRadius: CGFloat = 18, selected: Bool = false) -> some View {
        if selected {
            glassEffect(
                .regular.tint(Theme.accent.opacity(0.30)).interactive(),
                in: .rect(cornerRadius: cornerRadius)
            )
        } else {
            glassEffect(.regular.interactive(), in: .rect(cornerRadius: cornerRadius))
        }
    }

    /// Floating bar / pill surface (toolbars, batch action bar).
    func forgeGlassBar(cornerRadius: CGFloat = 22) -> some View {
        glassEffect(.regular, in: .rect(cornerRadius: cornerRadius))
    }

    /// Accent-tinted glass for primary call-to-action chips.
    func forgeGlassAccent(cornerRadius: CGFloat = 14) -> some View {
        glassEffect(.regular.tint(Theme.accent.opacity(0.55)).interactive(),
                    in: .rect(cornerRadius: cornerRadius))
    }
}
