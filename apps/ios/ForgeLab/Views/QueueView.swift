import SwiftUI

/// Main screen: yesterday's clip queue. Pull-to-refresh, date picker stuck on
/// "hier" by default per the morning workflow, multi-select for batch approve.
struct QueueView: View {
    let api: ForgeAPI
    /// When set, the view renders these clips and skips all networking. Used by
    /// the `--demo` launch path (CI screenshots). nil in normal operation.
    var demoClips: [Clip]? = nil
    @EnvironmentObject var settings: Settings

    @State private var clips: [Clip] = []
    @State private var loading = false
    @State private var error: String?
    @State private var date: Date = Calendar.current.date(byAdding: .day, value: -1, to: Date()) ?? Date()
    @State private var selection: Set<String> = []
    @State private var selectionMode = false
    @State private var settingsOpen = false
    @State private var batchInFlight = false

    var body: some View {
        NavigationStack {
            content
                .navigationTitle(Self.title(for: date))
                .toolbar { toolbar }
                .sheet(isPresented: $settingsOpen) {
                    NavigationStack { SettingsView() }
                }
                .refreshable { await load() }
                .task(id: date) { await load() }
        }
    }

    @ViewBuilder
    private var content: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            if loading && clips.isEmpty {
                ProgressView().scaleEffect(1.4)
            } else if clips.isEmpty {
                emptyState
            } else {
                list
            }
            if let error {
                VStack {
                    Spacer()
                    ErrorBanner(message: error)
                }
            }
        }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(clips) { clip in
                    NavigationLink {
                        ClipDetailView(api: api, clip: clip, demo: demoClips != nil)
                    } label: {
                        ClipCard(
                            clip: clip,
                            api: api,
                            selected: selection.contains(clip.id),
                            selectMode: selectionMode,
                            demo: demoClips != nil,
                        )
                    }
                    .buttonStyle(.plain)
                    .onLongPressGesture { toggleSelection(clip.id) }
                }
            }
            .padding(.horizontal)
            .padding(.bottom, selectionMode ? 80 : 12)
        }
        .overlay(alignment: .bottom) {
            if selectionMode { batchBar }
        }
    }

    private var batchBar: some View {
        HStack {
            Text("\(selection.count) sélectionné·s")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            Button(role: .cancel) {
                selection.removeAll()
                selectionMode = false
            } label: { Text("Annuler") }
            Button {
                Task { await batchApprove() }
            } label: {
                if batchInFlight { ProgressView() } else { Label("Approuver", systemImage: "checkmark") }
            }
            .buttonStyle(.borderedProminent)
            .disabled(selection.isEmpty || batchInFlight)
        }
        .padding()
        .background(Theme.surface)
        .cornerRadius(16)
        .padding()
    }

    @ToolbarContentBuilder
    private var toolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            DatePicker("Date", selection: $date, displayedComponents: .date)
                .labelsHidden()
        }
        ToolbarItem(placement: .topBarTrailing) {
            Menu {
                Button {
                    selectionMode.toggle()
                    if !selectionMode { selection.removeAll() }
                } label: {
                    Label(selectionMode ? "Quitter sélection" : "Sélection multiple",
                          systemImage: selectionMode ? "checkmark.circle" : "checklist")
                }
                Button { settingsOpen = true } label: {
                    Label("Réglages", systemImage: "gear")
                }
            } label: { Image(systemName: "ellipsis.circle") }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "moon.zzz")
                .font(.system(size: 48))
                .foregroundStyle(Theme.textSecondary)
            Text("Pas de clip pour cette date.")
                .font(.headline)
                .foregroundStyle(Theme.textSecondary)
            if let formatted = Self.dateFormatter.string(for: date) {
                Text(formatted)
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary.opacity(0.6))
            }
        }
    }

    // MARK: - Actions

    private func toggleSelection(_ id: String) {
        selectionMode = true
        if selection.contains(id) { selection.remove(id) } else { selection.insert(id) }
    }

    private func load() async {
        if let demoClips {
            clips = demoClips
            return
        }
        loading = true
        error = nil
        defer { loading = false }
        do {
            let resp = try await api.clipsByDate(date)
            clips = resp.items
        } catch let e as ApiError {
            error = e.errorDescription
        } catch {
            error = error.localizedDescription
        }
    }

    private func batchApprove() async {
        batchInFlight = true
        defer { batchInFlight = false }
        do {
            _ = try await api.batchApprove(ids: Array(selection))
            selection.removeAll()
            selectionMode = false
            await load()
        } catch let e as ApiError {
            error = e.errorDescription
        } catch {
            error = error.localizedDescription
        }
    }

    // MARK: - Formatting

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateStyle = .full
        return f
    }()

    static func title(for date: Date) -> String {
        let cal = Calendar.current
        if cal.isDateInToday(date) { return "Aujourd'hui" }
        if cal.isDateInYesterday(date) { return "Hier" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateFormat = "EEEE d MMM"
        return f.string(from: date).capitalized
    }
}

private struct ErrorBanner: View {
    let message: String
    var body: some View {
        Text(message)
            .font(.callout)
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Theme.danger.opacity(0.9))
            .cornerRadius(12)
            .padding()
            .transition(.move(edge: .bottom).combined(with: .opacity))
    }
}
