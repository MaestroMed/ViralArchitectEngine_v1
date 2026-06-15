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

    /// Queue renders yesterday's clips with their titles + scores.
    func testQueueShowsDemoClips() {
        let app = launchDemo()

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
        let app = launchDemo()
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
