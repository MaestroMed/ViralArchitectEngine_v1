import SwiftUI

/// Two-surface shell (iOS 26 Liquid Glass tab bar): the dashboard Home and the
/// date-browsable clip queue. Settings is reached from Home's toolbar.
struct MainTabView: View {
    let api: ForgeAPI
    var demoClips: [Clip]? = nil
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView(api: api, demoClips: demoClips, selectedTab: $selectedTab)
                .tabItem { Label("Accueil", systemImage: "house.fill") }
                .tag(0)
            QueueView(api: api, demoClips: demoClips)
                .tabItem { Label("Clips", systemImage: "rectangle.stack.fill") }
                .tag(1)
        }
        .tint(Theme.accent)
    }
}
