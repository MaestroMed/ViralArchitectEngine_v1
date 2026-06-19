import XCTest

/// Drives the real app in the iOS Simulator (demo mode, no backend) and asserts
/// the morning workflow renders + navigates. This is the "test the app in the
/// simulator" half: it actually launches ForgeLab, taps through it, and fails
/// the CI if a screen doesn't appear.
///
/// Each test also drops a screenshot attachment at key steps so the .xcresult
/// carries a visual trail (the CI additionally captures PNGs via simctl).
final class ForgeLabUITests: XCTestCase {

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    private func launchDemo(_ extraArgs: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--demo"] + extraArgs
        app.launch()
        return app
    }

    private func attach(_ app: XCUIApplication, _ name: String) {
        let shot = app.screenshot()
        let att = XCTAttachment(screenshot: shot)
        att.name = name
        att.lifetime = .keepAlways
        add(att)
    }

    /// The dashboard home is the default landing screen (brand + today section).
    func testHomeShowsDashboard() {
        let app = launchDemo()
        XCTAssertTrue(
            app.staticTexts["Aujourd'hui"].waitForExistence(timeout: 15),
            "Home dashboard 'Aujourd'hui' section should appear",
        )
        // Today's carousel surfaces the first demo clip's title.
        XCTAssertTrue(
            app.staticTexts["\"Le outplay de Cabochard là c'est ILLÉGAL\""].waitForExistence(timeout: 5),
            "Today's carousel should render the first demo clip",
        )
        attach(app, "home")
    }

    /// The Pilot cockpit lists the VOD library with engine status.
    func testPilotShowsLibrary() {
        let app = launchDemo(["--demo-screen", "pilot"])
        XCTAssertTrue(
            app.staticTexts["Bibliothèque"].waitForExistence(timeout: 15),
            "Pilot tab should show the 'Bibliothèque' section",
        )
        // A demo project name should render in the library.
        XCTAssertTrue(
            app.staticTexts["[Auto] STARK NIGHTTTT EYWAAAAAAAAA"].waitForExistence(timeout: 5),
            "Pilot library should render a demo project card",
        )
        attach(app, "pilot")
    }

    /// The Pilot jobs indicator opens a live Jobs sheet with the active job.
    func testPilotJobsSheetShowsActiveJob() {
        let app = launchDemo(["--demo-screen", "pilot"])
        // The demo seeds one running job → the chip reads "1 en cours".
        XCTAssertTrue(
            app.staticTexts["1 en cours"].waitForExistence(timeout: 15),
            "Pilot should show the live jobs indicator",
        )
        let jobs = app.buttons["pilot.jobs"]
        XCTAssertTrue(jobs.waitForExistence(timeout: 5), "Jobs indicator should be a button")
        jobs.tap()
        // The demo job is an 'analyze' job → "Analyse" label in the sheet.
        XCTAssertTrue(
            app.staticTexts["Analyse"].waitForExistence(timeout: 5),
            "Jobs sheet should list the active demo job",
        )
        attach(app, "jobs")
    }

    /// Tapping a project card opens its read-only detail.
    func testTapProjectOpensDetail() {
        let app = launchDemo(["--demo-screen", "pilot"])
        XCTAssertTrue(app.staticTexts["Bibliothèque"].waitForExistence(timeout: 15))

        let card = app.buttons["project-demo-proj-1"]
        XCTAssertTrue(card.waitForExistence(timeout: 5), "First project card should be tappable")
        card.tap()

        // Detail surfaces the metadata grid ("Segments" row).
        XCTAssertTrue(
            app.staticTexts["Segments"].waitForExistence(timeout: 5),
            "Project detail should show the metadata grid",
        )
        attach(app, "project-detail")
    }

    /// The Sources tab lists watched channels + detected VODs and the URL CTA.
    func testSourcesShowsChannelsAndVods() {
        let app = launchDemo(["--demo-screen", "sources"])
        XCTAssertTrue(
            app.staticTexts["Chaînes surveillées"].waitForExistence(timeout: 15),
            "Sources tab should show the channels section",
        )
        XCTAssertTrue(
            app.staticTexts["WAITING ROOM FRANCE-SÉNÉGAL"].waitForExistence(timeout: 5),
            "Sources should render a detected VOD",
        )
        // The paste-URL import CTA is present.
        XCTAssertTrue(app.buttons["sources.importUrl"].waitForExistence(timeout: 5))
        attach(app, "sources")
    }

    /// Queue renders yesterday's clips with their titles + scores.
    func testQueueShowsDemoClips() {
        // Route straight to the queue surface (home is now the default landing).
        let app = launchDemo(["--demo-screen", "queue"])

        // "Hier" is the nav title when the date is yesterday (demo default).
        XCTAssertTrue(
            app.staticTexts["Hier"].waitForExistence(timeout: 15),
            "Queue title 'Hier' should appear",
        )
        // At least the first demo clip's title is visible.
        let firstTitle = app.staticTexts["\"Le outplay de Cabochard là c'est ILLÉGAL\""]
        XCTAssertTrue(firstTitle.waitForExistence(timeout: 5), "First clip title should render")
        attach(app, "queue")
    }

    /// Tapping a clip opens the detail screen with the download action.
    func testTapClipOpensDetail() {
        let app = launchDemo(["--demo-screen", "queue"])
        XCTAssertTrue(app.staticTexts["Hier"].waitForExistence(timeout: 15))

        // The first card carries accessibilityIdentifier "clip-demo-1".
        let card = app.buttons["clip-demo-1"]
        XCTAssertTrue(card.waitForExistence(timeout: 5), "First clip card should be tappable")
        card.tap()

        let download = app.buttons["download-button"]
        XCTAssertTrue(
            download.waitForExistence(timeout: 5),
            "Detail screen should show the 'Télécharger + ouvrir TikTok' button",
        )
        attach(app, "detail")
    }

    /// Deep-link demo straight to the detail screen (used by the screenshot job).
    func testDeepLinkDetail() {
        let app = launchDemo(["--demo-screen", "detail"])
        let download = app.buttons["download-button"]
        XCTAssertTrue(download.waitForExistence(timeout: 15), "Detail should render on deep-link")
        attach(app, "detail-deeplink")
    }
}
