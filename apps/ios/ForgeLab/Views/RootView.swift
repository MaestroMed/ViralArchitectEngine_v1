import SwiftUI

/// Onboarding gate: until the user has saved the engine URL and an API key in
/// the keychain we route straight to Settings; everything else flows from
/// QueueView once configured.
struct RootView: View {
    @EnvironmentObject var settings: Settings

    var body: some View {
        Group {
            if AppLaunch.isDemo {
                // CI screenshots / design review: skip onboarding + network,
                // seed the real Views with DemoData. `--demo-screen detail`
                // deep-links straight to a clip detail for that screenshot.
                let demoAPI = ForgeAPI(baseURL: URL(string: "http://demo.local")!, apiKey: "demo")
                if AppLaunch.demoScreen == "detail", let first = DemoData.clips.first {
                    NavigationStack { ClipDetailView(api: demoAPI, clip: first, demo: true) }
                } else if AppLaunch.demoScreen == "settings" {
                    NavigationStack { SettingsView() }
                } else {
                    QueueView(api: demoAPI, demoClips: DemoData.clips)
                }
            } else if settings.isConfigured, let url = settings.baseURL, let key = settings.apiKey {
                QueueView(api: ForgeAPI(baseURL: url, apiKey: key))
            } else {
                NavigationStack { SettingsView() }
            }
        }
        .background(Theme.background.ignoresSafeArea())
    }
}
