import SwiftUI

/// Add a channel to watch. The parent performs the API call (so it owns the
/// channels list); this sheet just collects + validates input.
struct AddChannelSheet: View {
    /// (channelId, channelName, platform) → parent adds + dismisses.
    let onAdd: (String, String, String) async -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var platform = "twitch"
    @State private var channelId = ""
    @State private var channelName = ""
    @State private var submitting = false

    private var canSubmit: Bool {
        !channelId.trimmingCharacters(in: .whitespaces).isEmpty
            && !channelName.trimmingCharacters(in: .whitespaces).isEmpty
            && !submitting
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Plateforme", selection: $platform) {
                        Text("Twitch").tag("twitch")
                        Text("YouTube").tag("youtube")
                    }
                    .pickerStyle(.segmented)
                } header: { Text("Plateforme") }
                .listRowBackground(Color.clear.glassEffect(.regular, in: .rect(cornerRadius: 12)))

                Section {
                    TextField(platform == "twitch" ? "etostark" : "@chaine", text: $channelId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .accessibilityIdentifier("addchannel.id")
                    TextField("Nom affiché", text: $channelName)
                        .accessibilityIdentifier("addchannel.name")
                } header: {
                    Text("Chaîne")
                } footer: {
                    Text(platform == "twitch"
                         ? "L'identifiant de la chaîne Twitch (le login dans l'URL twitch.tv/…)."
                         : "Le handle YouTube (sans le @).")
                }
                .listRowBackground(Color.clear.glassEffect(.regular, in: .rect(cornerRadius: 12)))
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Ajouter une chaîne")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Annuler") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        submitting = true
                        Task {
                            await onAdd(channelId.trimmingCharacters(in: .whitespaces),
                                        channelName.trimmingCharacters(in: .whitespaces),
                                        platform)
                            // Self-contained: close regardless of parent state.
                            // The parent surfaces any error via its own toast.
                            submitting = false
                            dismiss()
                        }
                    } label: {
                        if submitting { ProgressView() } else { Text("Ajouter").bold() }
                    }
                    .disabled(!canSubmit)
                }
            }
        }
    }
}
