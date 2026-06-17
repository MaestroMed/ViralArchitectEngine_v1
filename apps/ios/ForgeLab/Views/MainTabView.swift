import SwiftUI

/// Three-surface shell (iOS 26 Liquid Glass tab bar):
/// - **Accueil**: today-focused dashboard.
/// - **Pilote**: the remote-pilot cockpit (engine status + whole VOD library).
/// - **Clips**: the date-browsable review queue.
/// Settings is reached from each tab's toolbar.
struct MainTabView: View {
    let api: ForgeAPI
    var demoClips: [Clip]? = nil
    var demoProjects: [Project]? = nil
    @State private var selectedTab: Int

    init(api: ForgeAPI, demoClips: [Clip]? = nil, demoProjects: [Project]? = nil, initialTab: Int = 0) {
        self.api = api
        self.demoClips = demoClips
        self.demoProjects = demoProjects
        _selectedTab = State(initialValue: initialTab)
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView(api: api, demoClips: demoClips, selectedTab: $selectedTab)
                .tabItem { Label("Accueil", systemImage: "house.fill") }
                .tag(0)
            PilotView(api: api, demoProjects: demoProjects)
                .tabItem { Label("Pilote", systemImage: "gauge.with.dots.needle.bottom.50percent") }
                .tag(1)
            QueueView(api: api, demoClips: demoClips)
                .tabItem { Label("Clips", systemImage: "rectangle.stack.fill") }
                .tag(2)
        }
        .tint(Theme.accent)
    }
}
