import Foundation

// Realtime spine. Connects to the engine's GLOBAL socket `/v1/ws`, which
// broadcasts `JOB_UPDATE` (job.to_dict()) and `PROJECT_UPDATE` ({id,status,…})
// to every client. Project-scoped firehose messages (ANALYSIS_PROGRESS /
// TRANSCRIPT_CHUNK) only reach project-channel subscribers, which we never join
// — so the global socket is exactly the live-job feed Pilote needs, no throttle.
//
// When the engine requires auth (FORGE_BIND_LAN / FORGE_REQUIRE_AUTH) the WS
// handshake is gated server-side by authorize_websocket(): the key must arrive
// as the `?key=` query param (URLSession also sends it as the X-API-Key header
// below, which the server accepts as a fallback). Reconnects with capped
// exponential backoff; an app-level ping keeps NAT/tunnel warm.
@MainActor
final class ForgeSocket: ObservableObject {
    /// Latest state per job id (active + recently-finished).
    @Published private(set) var liveJobs: [String: Job] = [:]
    /// Latest broadcast status per project id (overrides the fetched status).
    @Published private(set) var projectStatus: [String: String] = [:]
    @Published private(set) var connected = false

    private let baseURL: URL
    private let apiKey: String
    private let session: URLSession
    private var task: URLSessionWebSocketTask?
    private var readTask: Task<Void, Never>?
    private var pingTask: Task<Void, Never>?
    private var reconnectTask: Task<Void, Never>?
    private var attempt = 0
    private var running = false
    /// Bumped on every stop(); a reconnect scheduled in an older generation is
    /// invalidated even if its sleep completes after a later stop()/start().
    private var generation = 0

    init(baseURL: URL, apiKey: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.apiKey = apiKey
        self.session = session
    }

    var activeJobs: [Job] {
        liveJobs.values.filter(\.isActive).sorted { $0.id < $1.id }
    }

    func activeJob(forProject projectId: String) -> Job? {
        liveJobs.values.first { $0.projectId == projectId && $0.isActive }
    }

    // MARK: Lifecycle

    func start() {
        guard !running else { return }
        running = true
        connect()
    }

    func stop() {
        running = false
        generation &+= 1
        readTask?.cancel(); pingTask?.cancel(); reconnectTask?.cancel()
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        connected = false
    }

    private func connect() {
        guard running, let url = socketURL else { return }
        // Tear down any prior connection FULLY before opening a new one: cancel
        // the loops AND the old socket. Cancelling readTask alone doesn't
        // interrupt a blocking receive(); cancelling the socket makes it throw,
        // so the old read loop exits instead of running concurrently.
        readTask?.cancel(); pingTask?.cancel()
        task?.cancel(with: .goingAway, reason: nil)
        var req = URLRequest(url: url)
        req.timeoutInterval = 0   // long-lived
        req.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        let t = session.webSocketTask(with: req)
        task = t
        t.resume()
        connected = true
        readTask = Task { await readLoop(t) }
        pingTask = Task { await pingLoop(t) }
    }

    private var socketURL: URL? {
        guard var comps = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else { return nil }
        comps.scheme = (comps.scheme == "https") ? "wss" : "ws"
        comps.path = "/v1/ws"
        // Carry the key as `?key=` so the handshake authenticates even off-LAN
        // via the cloudflared tunnel. URLComponents percent-encodes the value.
        comps.queryItems = apiKey.isEmpty ? nil : [URLQueryItem(name: "key", value: apiKey)]
        return comps.url
    }

    // MARK: Receive

    private func readLoop(_ t: URLSessionWebSocketTask) async {
        do {
            while running && !Task.isCancelled && task === t {
                let message = try await t.receive()
                attempt = 0          // healthy traffic resets backoff
                handle(message)
            }
        } catch {
            // Only the current socket's failure should trigger a reconnect.
            guard running, task === t else { return }
            connected = false
            scheduleReconnect()
        }
    }

    private func handle(_ message: URLSessionWebSocketTask.Message) {
        let data: Data
        switch message {
        case .string(let s): data = Data(s.utf8)
        case .data(let d): data = d
        @unknown default: return
        }
        guard let env = try? JSONDecoder().decode(WSEnvelope.self, from: data) else { return }
        switch env.type {
        case "JOB_UPDATE":
            if let job = try? JSONDecoder().decode(WSPayload<Job>.self, from: data).payload {
                let wasActive = liveJobs[job.id]?.status != "completed"
                liveJobs[job.id] = job
                // Notify on the analyze/render → completed edge (clips are ready).
                if wasActive, job.status == "completed",
                   job.type == "analyze" || job.type == "render_final" {
                    LocalNotifier.clipsReady()
                }
            }
        case "PROJECT_UPDATE":
            if let p = try? JSONDecoder().decode(WSPayload<ProjectStatusUpdate>.self, from: data).payload {
                projectStatus[p.id] = p.status
            }
        default:
            break   // PONG / SUBSCRIBED / project-channel firehose — ignored here
        }
    }

    // MARK: Keep-alive + reconnect

    private func pingLoop(_ t: URLSessionWebSocketTask) async {
        while running && !Task.isCancelled {
            try? await Task.sleep(for: .seconds(25))
            guard running, task === t else { return }   // stop if socket replaced
            try? await t.send(.string("{\"type\":\"ping\"}"))
        }
    }

    private func scheduleReconnect() {
        guard running else { return }
        reconnectTask?.cancel()          // never accumulate pending reconnects
        attempt += 1
        let delay = min(pow(2.0, Double(attempt - 1)), 30)
        let gen = generation
        reconnectTask = Task {
            try? await Task.sleep(for: .seconds(delay))
            // gen guard survives a stop()+start() race the running flag can't.
            guard running, !Task.isCancelled, gen == generation else { return }
            connect()
        }
    }

    /// Merge already-running jobs (from a REST fetch) so the Jobs sheet isn't
    /// empty until the next broadcast. Does not change `connected`.
    func prime(_ jobs: [Job]) {
        for job in jobs where liveJobs[job.id] == nil || job.isActive {
            liveJobs[job.id] = job
        }
    }

    // MARK: Demo seeding (no network)

    /// Inject jobs for `--demo`/previews so the live overlays + Jobs sheet show
    /// something without a connection.
    func seedDemo(jobs: [Job]) {
        for job in jobs { liveJobs[job.id] = job }
        connected = true
    }
}

// MARK: - Wire format

private struct WSEnvelope: Decodable { let type: String }
private struct WSPayload<T: Decodable>: Decodable { let payload: T }
private struct ProjectStatusUpdate: Decodable {
    let id: String
    let status: String
    let name: String?
}
