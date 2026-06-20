import SwiftUI
import UIKit

/// After a batch export, the captions live here (one per clip) so each can be
/// copied independently — instead of every export clobbering the clipboard.
struct CaptionsSheet: View {
    let captions: [BundleDownloader.CaptionItem]
    @Environment(\.dismiss) private var dismiss
    @State private var copiedId: UUID?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    Text("Une légende par clip — copie-la au moment de poster.")
                        .font(.caption).foregroundStyle(Theme.textSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(captions) { item in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(item.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(Theme.textPrimary).lineLimit(1)
                            Text(item.caption)
                                .font(.caption).foregroundStyle(Theme.textSecondary).lineLimit(5)
                            Button {
                                UIPasteboard.general.string = item.caption
                                copiedId = item.id
                            } label: {
                                Label(copiedId == item.id ? "Copié ✓" : "Copier la légende",
                                      systemImage: copiedId == item.id ? "checkmark" : "doc.on.clipboard")
                                    .font(.caption.weight(.semibold))
                            }
                            .buttonStyle(.glass)
                            .tint(copiedId == item.id ? Theme.success : Theme.accent)
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .forgeGlassCard(cornerRadius: 16)
                    }
                }
                .padding()
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Légendes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Fermer") { dismiss() } } }
        }
    }
}
