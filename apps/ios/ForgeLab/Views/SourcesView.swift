import SwiftUI

/// "Feed the monster" — the Sources tab. Watch channels, check for new VODs,
/// and import (a detected VOD or a pasted URL) which kicks the
/// download→ingest→analyze pipeline on the Mac. Progress is then visible in
/// Pilote (job polling). Confirm-gated where it starts heavy compute.
struct SourcesView: View {
    let api: ForgeAPI
    var demoChannels: [WatchedChannel]? = nil
    var demoVods: [DetectedVOD]? = nil
    @EnvironmentObject var settings: Settings

    @State private var channels: [WatchedChannel] = []
    @State private var vods: [DetectedVOD] = []
    @State private var loading = false
    @State private var loadFailed = false
    @State private var busyChannels: Set<String> = []
    @State private var busyVods: Set<String> = []
    @State private var toast: String?
    @State private var toastTask: Task<Void, Never>?
    @State private var addChannelOpen = false
    @State private var urlImportOpen = false
    @State private var settingsOpen = false

    private var isDemo: Bool { demoChannels != nil || demoVods != nil }
    private var visibleVods: [DetectedVOD] { vods.filter { !$0.isIgnored } }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    urlImportCard
                    channelsSection
                    vodsSection
                }
                .padding(.horizontal)
                .padding(.top, 4)
                .padding(.bottom, 16)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Sources")
            .navigationBarTitleDisplayMode(.large)
            .toolbar { toolbar }
            .sheet(isPresented: $settingsOpen) { NavigationStack { SettingsView() } }
            .sheet(isPresented: $addChannelOpen) {
                AddChannelSheet { channelId, name, platform in
                    await addChannel(channelId: channelId, name: name, platform: platform)
                }
            }
            .sheet(isPresented: $urlImportOpen) {
                UrlImportSheet(api: api, demo: isDemo) { title in
                    urlImportOpen = false
                    flash("Import lancé : \(title) — suivi dans Pilote")
                }
            }
            .refreshable { await load() }
            .task { await load() }
            .overlay(alignment: .bottom) { toastView }
            // Tactile feedback on the key actions.
            .sensoryFeedback(.impact(flexibility: .soft), trigger: busyChannels)
            .sensoryFeedback(.impact(flexibility: .solid), trigger: busyVods)
            .sensoryFeedback(.selection, trigger: urlImportOpen)
        }
    }

    @ToolbarContentBuilder
    private var toolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            Button { addChannelOpen = true } label: {
                Image(systemName: "plus.circle.fill").foregroundStyle(Theme.accent)
            }
            .accessibilityLabel("Ajouter une chaîne")
            .accessibilityIdentifier("sources.addChannel")
        }
        ToolbarItem(placement: .topBarTrailing) {
            Button { settingsOpen = true } label: {
                Image(systemName: "gearshape.fill").foregroundStyle(Theme.textSecondary)
            }
            .accessibilityLabel("Réglages")
        }
    }

    // MARK: - URL import CTA

    private var urlImportCard: some View {
        Button { urlImportOpen = true } label: {
            HStack(spacing: 12) {
                Image(systemName: "link.badge.plus").font(.title2).foregroundStyle(.white)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Importer une VOD par URL").font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                    Text("Colle un lien Twitch ou YouTube").font(.caption).foregroundStyle(.white.opacity(0.85))
                }
                Spacer()
                Image(systemName: "arrow.right").foregroundStyle(.white)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .forgeGlassAccent(cornerRadius: 18)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Importer une VOD par URL")
        .accessibilityHint("Colle un lien Twitch ou YouTube")
        .accessibilityIdentifier("sources.importUrl")
    }

    // MARK: - Channels

    private var channelsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionHeader("Chaînes surveillées", count: channels.isEmpty ? nil : channels.count)
            if channels.isEmpty {
                placeholder(icon: "antenna.radiowaves.left.and.right",
                            title: "Aucune chaîne",
                            subtitle: "Ajoute une chaîne Twitch/YouTube pour détecter ses nouvelles VOD.")
            } else {
                GlassEffectContainer(spacing: 12) {
                    VStack(spacing: 12) {
                        ForEach(channels) { channel in
                            ChannelRow(
                                channel: channel,
                                busy: busyChannels.contains(channel.id),
                                onCheck: { Task { await checkChannel(channel) } },
                            )
                        }
                    }
                }
                if channels.count >= 2 {
                    Button {
                        Task { await checkAllChannels() }
                    } label: {
                        Label("Vérifier toutes les chaînes", systemImage: "arrow.triangle.2.circlepath")
                            .font(.subheadline.weight(.medium))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                    }
                    .buttonStyle(.glass)
                    .disabled(!busyChannels.isEmpty)
                }
            }
        }
    }

    private func checkAllChannels() async {
        for channel in channels { await checkChannel(channel) }
    }

    // MARK: - Detected VODs

    private var vodsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionHeader("VOD détectées", count: visibleVods.isEmpty ? nil : visibleVods.count)
            if loading && vods.isEmpty {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 30)
            } else if visibleVods.isEmpty {
                placeholder(icon: loadFailed ? "wifi.exclamationmark" : "film",
                            title: loadFailed ? "Sources indisponibles" : "Aucune VOD en attente",
                            subtitle: loadFailed
                                ? "Le moteur est injoignable."
                                : "Lance une vérification sur une chaîne pour détecter ses VOD.")
            } else {
                GlassEffectContainer(spacing: 12) {
                    VStack(spacing: 12) {
                        ForEach(visibleVods) { vod in
                            DetectedVodRow(
                                vod: vod,
                                busy: busyVods.contains(vod.id),
                                onImport: { Task { await importVod(vod) } },
                                onIgnore: { Task { await ignoreVod(vod) } },
                            )
                        }
                    }
                }
            }
        }
    }

    // MARK: - Shared bits

    private func sectionHeader(_ title: String, count: Int?) -> some View {
        SectionHeader(title: title, count: count)
    }

    private func placeholder(icon: String, title: String, subtitle: String) -> some View {
        EmptyStateCard(icon: icon, title: title, message: subtitle)
    }

    @ViewBuilder
    private var toastView: some View {
        if let toast {
            Text(toast)
                .font(.callout.weight(.medium)).foregroundStyle(.white)
                .padding(.horizontal, 16).padding(.vertical, 10)
                .background(Theme.accent.opacity(0.95)).clipShape(Capsule())
                .padding(.bottom, 12)
                .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    private func flash(_ message: String) {
        toastTask?.cancel()   // only one toast timer at a time
        withAnimation { toast = message }
        toastTask = Task {
            try? await Task.sleep(for: .seconds(3))
            if !Task.isCancelled { withAnimation { toast = nil } }
        }
    }

    // MARK: - Data + actions

    private func load() async {
        if isDemo {
            channels = demoChannels ?? []
            vods = demoVods ?? []
            return
        }
        loading = true; loadFailed = false
        defer { loading = false }
        async let ch = try? await api.fetchChannels()
        async let vd = try? await api.fetchDetectedVods(status: "new")
        channels = await ch ?? channels
        if let page = await vd {
            vods = page.items
        } else if channels.isEmpty {
            loadFailed = true
        }
    }

    private func checkChannel(_ channel: WatchedChannel) async {
        guard !isDemo else { flash("Mode démo — vérification simulée"); return }
        busyChannels.insert(channel.id)
        defer { busyChannels.remove(channel.id) }
        do {
            let result = try await api.checkChannel(id: channel.id)
            if let idx = channels.firstIndex(where: { $0.id == channel.id }) {
                channels[idx] = result.channel
            }
            // Merge fresh VODs to the front, de-duped (animate them in).
            let known = Set(vods.map(\.id))
            withAnimation(.easeInOut(duration: 0.3)) {
                vods.insert(contentsOf: result.newVods.filter { !known.contains($0.id) }, at: 0)
            }
            flash(result.newVods.isEmpty ? "Aucune nouvelle VOD" : "\(result.newVods.count) nouvelle(s) VOD")
        } catch let e as ApiError {
            flash(e.errorDescription ?? "Échec de la vérification")
        } catch {
            flash("Échec de la vérification")
        }
    }

    private func importVod(_ vod: DetectedVOD) async {
        guard !isDemo else { flash("Mode démo — import simulé"); return }
        busyVods.insert(vod.id)
        defer { busyVods.remove(vod.id) }
        do {
            _ = try await api.importVod(id: vod.id)
            markVod(vod.id, status: "imported")
            flash("Import lancé — suivi dans Pilote")
        } catch let e as ApiError {
            flash(e.errorDescription ?? "Échec de l'import")
        } catch {
            flash("Échec de l'import")
        }
    }

    private func ignoreVod(_ vod: DetectedVOD) async {
        guard !isDemo else { vods.removeAll { $0.id == vod.id }; return }
        busyVods.insert(vod.id)
        defer { busyVods.remove(vod.id) }
        do {
            _ = try await api.setVodStatus(id: vod.id, status: "ignored")
            markVod(vod.id, status: "ignored")
        } catch {
            flash("Échec")
        }
    }

    /// The sheet dismisses itself after this returns; we just do the work + toast.
    private func addChannel(channelId: String, name: String, platform: String) async {
        guard !isDemo else { flash("Mode démo"); return }
        do {
            let channel = try await api.addChannel(channelId: channelId, channelName: name, platform: platform, displayName: name)
            if !channels.contains(where: { $0.id == channel.id }) { channels.insert(channel, at: 0) }
            flash("Chaîne ajoutée : \(channel.title)")
        } catch let e as ApiError {
            flash(e.errorDescription ?? "Échec de l'ajout")
        } catch {
            flash("Échec de l'ajout")
        }
    }

    /// Replace a VOD's status in-place (status comes back camelCase from PATCH;
    /// here we just need the local list to reflect imported/ignored).
    private func markVod(_ id: String, status: String) {
        guard let idx = vods.firstIndex(where: { $0.id == id }) else { return }
        let v = vods[idx]
        vods[idx] = DetectedVOD(
            id: v.id, externalId: v.externalId, title: v.title, channelId: v.channelId,
            channelName: v.channelName, platform: v.platform, url: v.url,
            thumbnailUrl: v.thumbnailUrl, duration: v.duration, publishedAt: v.publishedAt,
            viewCount: v.viewCount, status: status, projectId: v.projectId,
            estimatedScore: v.estimatedScore, detectedAt: v.detectedAt,
        )
    }
}

// MARK: - Rows

private struct ChannelRow: View {
    let channel: WatchedChannel
    let busy: Bool
    let onCheck: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            avatar
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(channel.title).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                HStack(spacing: 6) {
                    Text(channel.platform.capitalized).font(.caption2).foregroundStyle(Theme.textSecondary)
                    if let last = channel.lastCheckRelative {
                        Text("· vérifié \(last)").font(.caption2).foregroundStyle(Theme.textSecondary.opacity(0.8))
                    } else {
                        Text("· jamais vérifié").font(.caption2).foregroundStyle(Theme.textSecondary.opacity(0.8))
                    }
                }
            }
            .accessibilityElement(children: .combine)
            Spacer(minLength: 0)
            Button(action: onCheck) {
                if busy {
                    ProgressView().controlSize(.small).tint(Theme.accent)
                } else {
                    Image(systemName: "arrow.triangle.2.circlepath").foregroundStyle(Theme.accent)
                }
            }
            .buttonStyle(.plain)
            .disabled(busy)
            .accessibilityLabel("Vérifier \(channel.title)")
            .accessibilityIdentifier("channel-check-\(channel.id)")
        }
        .padding(12)
        .forgeGlassCard(cornerRadius: Theme.Radius.md)
    }

    @ViewBuilder
    private var avatar: some View {
        // Channel avatars are external CDN URLs (Twitch/YouTube) → plain AsyncImage.
        if let s = channel.profileImageUrl, let url = URL(string: s) {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let img): img.resizable().aspectRatio(contentMode: .fill)
                default: avatarFallback
                }
            }
            .frame(width: 42, height: 42).clipShape(Circle())
        } else {
            avatarFallback.frame(width: 42, height: 42).clipShape(Circle())
        }
    }

    private var avatarFallback: some View {
        Circle().fill(Theme.accentSoft)
            .overlay(Text(channel.title.prefix(1).uppercased()).font(.headline).foregroundStyle(Theme.accent))
    }
}

private struct DetectedVodRow: View {
    let vod: DetectedVOD
    let busy: Bool
    let onImport: () -> Void
    let onIgnore: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                thumbnail
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 5) {
                    Text(vod.title).font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.textPrimary).lineLimit(2)
                    Text(vod.channelName).font(.caption).foregroundStyle(Theme.textSecondary)
                    HStack(spacing: 10) {
                        if let d = vod.durationLabel { meta(d, "clock") }
                        if let v = vod.viewsLabel { Text(v).font(.caption2).foregroundStyle(Theme.textSecondary) }
                        if let s = vod.estimatedScore { ScoreBadge(score: s) }
                    }
                }
                .accessibilityElement(children: .combine)
                Spacer(minLength: 0)
            }
            actions
        }
        .padding(12)
        .forgeGlassCard(cornerRadius: Theme.Radius.md)
    }

    @ViewBuilder
    private var thumbnail: some View {
        // VOD thumbnails are external Twitch/YouTube URLs → plain AsyncImage.
        Group {
            if let s = vod.thumbnailUrl, let url = URL(string: s) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img): img.resizable().aspectRatio(contentMode: .fill)
                    case .failure: thumbFallback
                    default: thumbFallback.overlay(ProgressView())
                    }
                }
            } else {
                thumbFallback
            }
        }
        .frame(width: 104, height: 58)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var thumbFallback: some View {
        Rectangle().fill(Theme.background).overlay(Image(systemName: "film").foregroundStyle(Theme.textSecondary))
    }

    @ViewBuilder
    private var actions: some View {
        if vod.isImported {
            HStack(spacing: 6) {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.success)
                Text("Importé").font(.caption.weight(.semibold)).foregroundStyle(Theme.success)
            }
        } else {
            HStack(spacing: 10) {
                Button(action: onImport) {
                    HStack(spacing: 6) {
                        if busy { ProgressView().controlSize(.small) }
                        else { Image(systemName: "square.and.arrow.down.fill") }
                        Text(busy ? "Import…" : "Importer")
                    }
                    .font(.caption.weight(.semibold))
                }
                .buttonStyle(.glassProminent)
                .tint(Theme.accent)
                .opacity(busy ? 0.6 : 1)
                .disabled(busy)
                .accessibilityIdentifier("vod-import-\(vod.id)")

                Button(action: onIgnore) {
                    Text("Ignorer").font(.caption.weight(.medium)).foregroundStyle(Theme.textSecondary)
                }
                .buttonStyle(.plain)
                .disabled(busy)
                Spacer()
            }
        }
    }

    private func meta(_ value: String, _ icon: String) -> some View {
        Label(value, systemImage: icon).font(.caption2).foregroundStyle(Theme.textSecondary)
    }
}
