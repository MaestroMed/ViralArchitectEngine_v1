import SwiftUI

/// Live jobs list (from the WS feed). Active jobs first, with progress + stage
/// and a one-tap cancel. Read + job-control only — no destructive admin.
struct JobsSheet: View {
    let jobs: [Job]
    /// projectId → display name, for labelling each job's target.
    let projectName: (String) -> String?
    let onCancel: (Job) async -> Void
    var demo: Bool = false
    @Environment(\.dismiss) private var dismiss

    @State private var cancelling: Set<String> = []
    @State private var confirmCancel: Job?

    private var sorted: [Job] {
        jobs.sorted { a, b in
            if a.isActive != b.isActive { return a.isActive }   // active first
            return a.createdAt > b.createdAt                      // then most recent
        }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                if sorted.isEmpty {
                    empty
                } else {
                    VStack(spacing: 12) {
                        ForEach(sorted) { job in row(job) }
                    }
                    .padding()
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Jobs")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Fermer") { dismiss() } }
            }
            .sensoryFeedback(.warning, trigger: confirmCancel)   // haptic on cancel-confirm
            .confirmationDialog(
                "Annuler ce job ?",
                isPresented: Binding(get: { confirmCancel != nil }, set: { if !$0 { confirmCancel = nil } }),
                titleVisibility: .visible,
            ) {
                Button("Annuler le job", role: .destructive) {
                    if let job = confirmCancel { Task { await cancel(job) } }
                }
                Button("Garder", role: .cancel) {}
            }
        }
    }

    private var empty: some View {
        VStack(spacing: 10) {
            Image(systemName: "bolt.horizontal.circle").font(.largeTitle).foregroundStyle(Theme.textSecondary)
                .accessibilityHidden(true)
            Text("Aucun job actif").font(.headline).foregroundStyle(Theme.textPrimary)
            Text("Les imports, ingestions et analyses s'afficheront ici en temps réel.")
                .font(.subheadline).foregroundStyle(Theme.textSecondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(.top, 80).padding(.horizontal, 32)
    }

    private func row(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(job.typeLabel).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.textPrimary)
                Spacer()
                Text(job.statusLabel)
                    .font(.caption2.weight(.semibold)).foregroundStyle(.white)
                    .padding(.horizontal, 7).padding(.vertical, 2)
                    .background(job.statusColor).clipShape(Capsule())
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(job.typeLabel), \(job.statusLabel)")
            if let pid = job.projectId, let name = projectName(pid) {
                Text(name).font(.caption).foregroundStyle(Theme.textSecondary).lineLimit(1)
            }
            if job.isActive {
                ProgressView(value: job.fraction).tint(Theme.accent)
                    .forgeShimmer(active: true)
                HStack {
                    if let stage = job.stage, !stage.isEmpty {
                        Text(stage).font(.caption2).foregroundStyle(Theme.textSecondary)
                    }
                    Spacer()
                    Text("\(Int(job.progress))%").font(.caption2.monospacedDigit()).foregroundStyle(Theme.textSecondary)
                    Button {
                        confirmCancel = job
                    } label: {
                        if cancelling.contains(job.id) {
                            ProgressView().controlSize(.mini)
                        } else {
                            Text("Annuler").font(.caption2.weight(.semibold)).foregroundStyle(Theme.danger)
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(cancelling.contains(job.id))
                    .accessibilityLabel("Annuler \(job.typeLabel)")
                    .accessibilityIdentifier("job-cancel-\(job.id)")
                }
            } else if let err = job.error, !err.isEmpty {
                Text(err).font(.caption).foregroundStyle(Theme.danger).lineLimit(2)
            }
        }
        .padding(14)
        .forgeGlassCard(cornerRadius: Theme.Radius.md)
    }

    private func cancel(_ job: Job) async {
        cancelling.insert(job.id)
        defer { cancelling.remove(job.id) }
        await onCancel(job)
    }
}
