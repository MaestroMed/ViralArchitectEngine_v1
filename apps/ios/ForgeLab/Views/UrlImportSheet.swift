import SwiftUI

/// Paste a Twitch/YouTube URL → preview the video metadata → import (which
/// kicks the full download→ingest→analyze pipeline on the Mac).
struct UrlImportSheet: View {
    let api: ForgeAPI
    var demo: Bool = false
    /// Called with the imported video's title once the pipeline job is queued.
    let onImported: (String) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var url = ""
    @State private var info: VideoInfo?
    @State private var previewing = false
    @State private var importing = false
    @State private var error: String?

    private var canPreview: Bool {
        let u = url.trimmingCharacters(in: .whitespaces)
        return (u.contains("twitch.tv") || u.contains("youtu")) && !previewing
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    field
                    if let info { preview(info) }
                    if let error {
                        Text(error).font(.subheadline).foregroundStyle(Theme.danger)
                    }
                    Spacer(minLength: 0)
                }
                .padding(20)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Importer une VOD")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    // Block dismiss mid-import so the completion callback never
                    // fires into an unmounted view.
                    Button("Fermer") { dismiss() }.disabled(importing)
                }
            }
        }
    }

    private var field: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Lien de la VOD").font(.caption).foregroundStyle(Theme.textSecondary)
            TextField("https://twitch.tv/videos/…", text: $url)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .padding(12)
                .forgeGlassCard(cornerRadius: 12)
                .accessibilityIdentifier("urlimport.field")
            Button {
                Task { await preview() }
            } label: {
                HStack {
                    if previewing { ProgressView().controlSize(.small) }
                    Text(previewing ? "Récupération…" : "Aperçu")
                }
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
            }
            .buttonStyle(.glass)
            .disabled(!canPreview)
        }
    }

    private func preview(_ info: VideoInfo) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let s = info.thumbnailUrl, let u = URL(string: s) {
                AsyncImage(url: u) { phase in
                    if case .success(let img) = phase {
                        img.resizable().aspectRatio(contentMode: .fill)
                    } else {
                        Rectangle().fill(Theme.surface)
                    }
                }
                .frame(height: 180).frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            Text(info.title).font(.headline).foregroundStyle(Theme.textPrimary).lineLimit(3)
            HStack(spacing: 12) {
                if let c = info.channel { Label(c, systemImage: "person.fill").font(.caption) }
                if let d = info.durationLabel { Label(d, systemImage: "clock").font(.caption) }
                if let p = info.platform { Text(p.capitalized).font(.caption) }
            }
            .foregroundStyle(Theme.textSecondary)

            Button {
                Task { await runImport(title: info.title) }
            } label: {
                HStack {
                    if importing { ProgressView().controlSize(.small).tint(.white) }
                    else { Image(systemName: "square.and.arrow.down.fill") }
                    Text(importing ? "Import en cours…" : "Importer + traiter")
                }
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity).padding(.vertical, 12)
            }
            .buttonStyle(.glassProminent)
            .tint(Theme.accent)
            .disabled(importing)
            .accessibilityIdentifier("urlimport.confirm")
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: 18)
    }

    // MARK: Actions

    private func preview() async {
        error = nil
        if demo {
            info = VideoInfo(id: "demo", title: "WAITING ROOM FRANCE-SÉNÉGAL",
                             description: nil, duration: 8280, thumbnailUrl: nil,
                             channel: "EtoStark", channelId: "etostark", uploadDate: nil,
                             viewCount: 24500, url: url, platform: "twitch")
            return
        }
        previewing = true
        defer { previewing = false }
        do {
            info = try await api.urlInfo(url: url.trimmingCharacters(in: .whitespaces))
        } catch let e as ApiError {
            error = e.errorDescription
        } catch {
            self.error = "Impossible de récupérer la vidéo"
        }
    }

    private func runImport(title: String) async {
        error = nil
        if demo {
            onImported(title)
            return
        }
        importing = true
        defer { importing = false }
        do {
            _ = try await api.importUrl(url: url.trimmingCharacters(in: .whitespaces))
            onImported(title)
        } catch let e as ApiError {
            error = e.errorDescription
        } catch {
            self.error = "Échec de l'import"
        }
    }
}
