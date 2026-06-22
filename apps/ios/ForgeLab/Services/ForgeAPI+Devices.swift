import Foundation

/// Push-device registration. The app POSTs its APNs device token to the engine
/// so a backgrounded phone can be woken with a real remote notification when
/// clips are ready for QC. Mirrors the engine's `/v1/devices/register` upsert.
extension ForgeAPI {

    private struct RegisterDeviceRequest: Encodable {
        let token: String
        let platform: String
        let bundleId: String
    }

    /// Register (or refresh) this device's APNs token with the engine.
    /// Idempotent server-side — safe to call on every launch / token refresh.
    func registerDevice(token: String) async throws {
        let bundleId = Bundle.main.bundleIdentifier ?? "com.maestromed.forgelab"
        _ = try await request(
            EmptyDeviceResponse.self,
            path: "/v1/devices/register",
            method: "POST",
            body: RegisterDeviceRequest(token: token, platform: "ios", bundleId: bundleId),
        )
    }

    private struct EmptyDeviceResponse: Decodable {}
}
