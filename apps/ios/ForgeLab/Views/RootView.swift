import SwiftUI

/// Onboarding gate: until the user has saved the engine URL and an API key in
/// the keychain we route straight to Settings; everything else flows from
/// QueueView once configured.
struct RootView: View {
    @EnvironmentObject var settings: Settings

    var body: some View {
        Group {
            if settings.isConfigured, let url = settings.baseURL, let key = settings.apiKey {
                QueueView(api: ForgeAPI(baseURL: url, apiKey: key))
            } else {
                NavigationStack { SettingsView() }
            }
        }
        .background(Theme.background.ignoresSafeArea())
    }
}
