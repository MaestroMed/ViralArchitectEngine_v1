import SwiftUI

/// First-run + edit screen. Single concern: get a working (baseURL, apiKey)
/// pair into the keychain. We hit `/health` to verify the URL is reachable
/// before saving so the user gets immediate feedback instead of discovering
/// the typo on the Queue screen.
struct SettingsView: View {
    @EnvironmentObject var settings: Settings
    @Environment(\.dismiss) var dismiss

    @State private var host: String = ""
    @State private var port: String = "8420"
    @State private var apiKey: String = ""
    @State private var testing = false
    @State private var feedback: Feedback?

    enum Feedback: Equatable {
        case success(version: String)
        case failure(String)
        var isOk: Bool { if case .success = self { return true } else { return false } }
    }

    var body: some View {
        Form {
            if !settings.isConfigured {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Bienvenue 👋")
                            .font(.title2.weight(.bold)).foregroundStyle(Theme.textPrimary)
                        Text("Connecte l'app au moteur FORGE qui tourne sur ton Mac pour piloter tes clips à distance — surveiller, reviewer, exporter.")
                            .font(.subheadline).foregroundStyle(Theme.textSecondary)
                    }
                    .padding(.vertical, 4)
                }
                .listRowBackground(Color.clear)
            }

            Section {
                TextField("192.168.1.50", text: $host)
                    .textContentType(.URL)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                TextField("8420", text: $port)
                    .keyboardType(.numberPad)
            } header: { Text("Moteur") } footer: {
                Text("IP locale du PC qui fait tourner le moteur. Active FORGE_BIND_LAN=1 dans .env pour l'autoriser à écouter sur le WiFi.")
            }

            Section {
                SecureField("forge_…", text: $apiKey)
                    .textContentType(.password)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
            } header: { Text("Clé API") } footer: {
                Text("Génère-la sur ton PC: `python -m forge_engine.scripts.seed_api_key create 'iPhone Air'`. Tu la vois une fois — copie-la ici directement.")
            }

            if let feedback {
                Section {
                    Label(
                        feedback.isOk ? "Connexion OK" : feedbackText(feedback),
                        systemImage: feedback.isOk ? "checkmark.circle.fill" : "xmark.octagon.fill",
                    )
                    .foregroundStyle(feedback.isOk ? Theme.success : Theme.danger)
                }
            }

            Section {
                Button {
                    Task { await test() }
                } label: {
                    if testing {
                        ProgressView()
                    } else {
                        Label("Tester la connexion", systemImage: "antenna.radiowaves.left.and.right")
                    }
                }
                .buttonStyle(.glass)
                .disabled(testing || !canTest)

                Button {
                    save()
                } label: {
                    Label("Enregistrer", systemImage: "checkmark")
                        .frame(maxWidth: .infinity)
                }
                .disabled(!canSave)
                .buttonStyle(.glassProminent)
                .tint(Theme.accent)
            }

            if settings.isConfigured {
                Section {
                    Button(role: .destructive) {
                        settings.clear()
                        host = ""
                        port = "8420"
                        apiKey = ""
                        feedback = nil
                    } label: {
                        Label("Oublier ce moteur", systemImage: "trash")
                    }
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.background.ignoresSafeArea())
        .listRowBackground(
            Color.clear.glassEffect(.regular, in: .rect(cornerRadius: Theme.Radius.sm))
        )
        .navigationTitle("Réglages")
        .onAppear(perform: hydrateFromSettings)
    }

    private func feedbackText(_ f: Feedback) -> String {
        if case .failure(let why) = f { return why }
        return ""
    }

    private var canTest: Bool { url != nil }
    private var canSave: Bool { url != nil && !apiKey.isEmpty && feedback?.isOk == true }
    private var url: URL? {
        let trimmed = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, let p = Int(port), p > 0, p < 65_536 else { return nil }
        let scheme = trimmed.hasPrefix("http") ? "" : "http://"
        return URL(string: "\(scheme)\(trimmed):\(p)")
    }

    private func hydrateFromSettings() {
        if let existing = settings.baseURL {
            host = existing.host ?? ""
            port = existing.port.map(String.init) ?? "8420"
        }
        if let k = settings.apiKey { apiKey = k }
    }

    private func test() async {
        guard let url else { return }
        testing = true
        feedback = nil
        defer { testing = false }
        do {
            let api = ForgeAPI(baseURL: url, apiKey: apiKey)
            try await api.ping()
            feedback = .success(version: "ok")
        } catch let error as ApiError {
            feedback = .failure(error.errorDescription ?? "Erreur inconnue")
        } catch {
            feedback = .failure(error.localizedDescription)
        }
    }

    private func save() {
        guard let url else { return }
        settings.save(baseURL: url, apiKey: apiKey)
        dismiss()
    }
}
