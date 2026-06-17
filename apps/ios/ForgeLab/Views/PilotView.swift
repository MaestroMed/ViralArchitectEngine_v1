import SwiftUI

/// The remote-pilot cockpit: live engine status + the whole VOD library.
/// Read-only — it monitors the engine and lets Mehdi drill into any project,
/// but never triggers compute or admin actions (those stay Mac-side).
struct PilotView: View {
    let api: ForgeAPI
    /// When set, render these instead of networking (--demo / previews).
    var demoProjects: [Project]? = nil
    @EnvironmentObject var settings: Settings

    @State private var projects: [Project] = []
    @State private var health: HealthResponse?
    @State private var caps: Capabilities?
    @State private var jobStats: JobStats?
    @State private var loading = false
    @State private var loadFailed = false
    @State private var settingsOpen = false

    private var isDemo: Bool { demoProjects != nil }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    statusHeader
                    libraryHeader
                    libraryBody
                }
                .padding(.horizontal)
                .padding(.top, 4)
                .padding(.bottom, 16)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Pilote")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { settingsOpen = true } label: {
                        Image(systemName: "gearshape.fill").foregroundStyle(Theme.textSecondary)
                    }
                    .accessibilityIdentifier("pilot.settings")
                }
            }
            .sheet(isPresented: $settingsOpen) { NavigationStack { SettingsView() } }
            .refreshable { await load() }
            .task { await load() }
        }
    }

    // MARK: - Engine status header

    private var engineUp: Bool { health != nil }

    private var statusHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Circle().fill(engineUp ? Theme.success : Theme.danger).frame(width: 9, height: 9)
                Text(engineUp ? "Moteur connecté" : "Moteur injoignable")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.textPrimary)
                if let v = health?.version {
                    Text("v\(v)").font(.caption).foregroundStyle(Theme.textSecondary)
                }
                Spacer(minLength: 0)
                jobsIndicator
            }
            if engineUp { capabilityChips }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .forgeGlassCard(cornerRadius: 20)
        .accessibilityIdentifier("pilot.status")
    }

    @ViewBuilder
    private var jobsIndicator: some View {
        let active = jobStats?.active ?? 0
        if active > 0 {
            HStack(spacing: 6) {
                ProgressView().controlSize(.mini).tint(Theme.accent)
                Text("\(active) en cours")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.accent)
            }
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Theme.accentSoft).clipShape(Capsule())
        } else if engineUp {
            Text("au repos").font(.caption).foregroundStyle(Theme.textSecondary)
        }
    }

    private var capabilityChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                if let w = caps?.whisperLabel { capChip(w, "waveform") }
                if caps?.ffmpeg?.hasLibass == true { capChip("Sous-titres", "captions.bubble") }
                capChip(caps?.gpu?.available == true ? "GPU" : "CPU",
                        caps?.gpu?.available == true ? "cpu" : "cpu")
                if let free = caps?.freeSpaceLabel { capChip("\(free) libres", "internaldrive") }
            }
        }
    }

    private func capChip(_ text: String, _ icon: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon).font(.system(size: 9))
            Text(text).font(.caption2.weight(.medium))
        }
        .foregroundStyle(Theme.textSecondary)
        .padding(.horizontal, 9).padding(.vertical, 4)
        .background(Theme.textSecondary.opacity(0.12))
        .clipShape(Capsule())
    }

    // MARK: - Library

    private var libraryHeader: some View {
        HStack {
            Text("Bibliothèque").font(.title3.weight(.bold)).foregroundStyle(Theme.textPrimary)
            Spacer()
            if !projects.isEmpty {
                Text("\(projects.count)")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.textSecondary)
            }
        }
        .padding(.top, 2)
    }

    @ViewBuilder
    private var libraryBody: some View {
        if loading && projects.isEmpty {
            ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
        } else if projects.isEmpty {
            emptyState
        } else {
            GlassEffectContainer(spacing: 14) {
                LazyVStack(spacing: 14) {
                    ForEach(projects) { project in
                        NavigationLink {
                            ProjectDetailView(api: api, project: project, demo: isDemo)
                        } label: {
                            ProjectCard(project: project, api: api, demo: isDemo)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("project-\(project.id)")
                    }
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: loadFailed ? "wifi.exclamationmark" : "tray")
                .font(.largeTitle).foregroundStyle(Theme.textSecondary)
            Text(loadFailed ? "Bibliothèque indisponible" : "Aucun projet")
                .font(.headline).foregroundStyle(Theme.textPrimary)
            Text(loadFailed
                 ? "Le moteur est injoignable. Vérifie l'URL et la clé dans les réglages."
                 : "Les VOD traitées par le moteur apparaîtront ici.")
                .font(.subheadline).foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(28)
        .forgeGlassCard(cornerRadius: 18)
    }

    // MARK: - Data

    private func load() async {
        if let demoProjects {
            projects = demoProjects
            health = HealthResponse(status: "healthy", version: "demo",
                                    services: HealthServices(ffmpeg: true, whisper: true, nvenc: false, database: true))
            caps = Capabilities(
                ffmpeg: Capabilities.FFmpeg(version: "8.1.1", hasNvenc: false, hasLibass: true),
                whisper: Capabilities.Whisper(available: true, currentModel: "large-v3", device: "cpu", computeType: "float32", modelLoaded: false),
                gpu: Capabilities.GPU(available: false, count: 0),
                storage: Capabilities.Storage(libraryPath: "/FORGE_LIBRARY", freeSpace: 459_318_706_176),
            )
            jobStats = JobStats(pending: 0, running: 1, completed: 12, failed: 0, cancelled: 0)
            return
        }
        loading = true; loadFailed = false
        defer { loading = false }
        // Status surfaces are best-effort; a failure shouldn't blank the library.
        health = try? await api.request(HealthResponse.self, path: "/health", needsAuth: false)
        async let capsResult = try? await api.fetchCapabilities()
        async let statsResult = try? await api.fetchJobStats()
        caps = await capsResult
        jobStats = (await statsResult)?.stats
        do {
            projects = try await api.fetchProjects(pageSize: 100).items
        } catch {
            loadFailed = true
        }
    }
}
