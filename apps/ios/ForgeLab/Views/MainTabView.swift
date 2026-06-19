import SwiftUI

/// Four-surface shell (iOS 26 Liquid Glass tab bar):
/// - **Accueil** (0): today-focused dashboard.
/// - **Pilote** (1): remote-pilot cockpit (engine status + whole VOD library).
/// - **Sources** (2): watch channels + import VODs (feed the engine).
/// - **Clips** (3): the date-browsable review queue.
/// Tags are stable so inserting a tab never shifts another's tag.
/// Settings is reached from each tab's toolbar.
struct MainTabView: View {
    let api: ForgeAPI
    var demoClips: [Clip]? = nil
    var demoProjects: [Project]? = nil
    var demoChannels: [WatchedChannel]? = nil
    var demoVods: [DetectedVOD]? = nil
    @State private var selectedTab: Int

    init(api: ForgeAPI,
         demoClips: [Clip]? = nil,
         demoProjects: [Project]? = nil,
         demoChannels: [WatchedChannel]? = nil,
         demoVods: [DetectedVOD]? = nil,
         initialTab: Int = 0) {
        self.api = api
        self.demoClips = demoClips
        self.demoProjects = demoProjects
        self.demoChannels = demoChannels
        self.demoVods = demoVods
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
            SourcesView(api: api, demoChannels: demoChannels, demoVods: demoVods)
                .tabItem { Label("Sources", systemImage: "antenna.radiowaves.left.and.right") }
                .tag(2)
            QueueView(api: api, demoClips: demoClips)
                .tabItem { Label("Clips", systemImage: "rectangle.stack.fill") }
                .tag(3)
        }
        .tint(Theme.accent)
    }
}
