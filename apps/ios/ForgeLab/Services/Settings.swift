import Foundation
import Security

/// Persistent configuration: engine base URL and API key, kept in the keychain
/// so it survives reinstalls and isn't readable by other processes.
///
/// Why keychain and not UserDefaults: the API key is a bearer credential. iOS
/// backs up UserDefaults to iCloud (cleartext) unless explicitly excluded; the
/// keychain attributes below pin storage to this device only and never sync.
final class Settings: ObservableObject, @unchecked Sendable {
    static let shared = Settings()

    private enum Key: String {
        case baseURL = "forgelab.baseURL"
        case apiKey = "forgelab.apiKey"
    }

    @Published private(set) var baseURL: URL?
    @Published private(set) var apiKey: String?

    var isConfigured: Bool { baseURL != nil && apiKey?.isEmpty == false }

    private init() {
        baseURL = (readKeychain(.baseURL) ?? "").nonEmpty.flatMap(URL.init(string:))
        apiKey = readKeychain(.apiKey)
    }

    func save(baseURL: URL, apiKey: String) {
        writeKeychain(.baseURL, baseURL.absoluteString)
        writeKeychain(.apiKey, apiKey)
        DispatchQueue.main.async {
            self.baseURL = baseURL
            self.apiKey = apiKey
        }
    }

    func clear() {
        deleteKeychain(.baseURL)
        deleteKeychain(.apiKey)
        DispatchQueue.main.async {
            self.baseURL = nil
            self.apiKey = nil
        }
    }

    // MARK: - Keychain primitives

    private func baseQuery(_ key: Key) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.maestromed.forgelab",
            kSecAttrAccount as String: key.rawValue,
            // ThisDeviceOnly: never iCloud-synced; unlocked-after-first-unlock so
            // background tasks (none today, but cheap insurance) can read it.
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
    }

    private func readKeychain(_ key: Key) -> String? {
        var query = baseQuery(key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func writeKeychain(_ key: Key, _ value: String) {
        guard let data = value.data(using: .utf8) else { return }
        let query = baseQuery(key)
        let attrs: [String: Any] = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
        if status == errSecItemNotFound {
            var add = query
            add[kSecValueData as String] = data
            SecItemAdd(add as CFDictionary, nil)
        }
    }

    private func deleteKeychain(_ key: Key) {
        SecItemDelete(baseQuery(key) as CFDictionary)
    }
}

private extension Optional where Wrapped == String {
    var nonEmpty: String? {
        guard let s = self, !s.isEmpty else { return nil }
        return s
    }
}
