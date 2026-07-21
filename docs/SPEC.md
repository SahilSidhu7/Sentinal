# VibeSentinel — Product & Engineering Spec Sheet

Version: 0.1 (draft)
Status: Pre-build
Owner: Sahil Sidhu

---

## 1. Product Summary

VibeSentinel is a full-stack, AI-powered security monitoring platform for local machines and small self-hosted servers. It watches a target (folder, repo, or container), scans it for security issues, explains findings in plain English via a local LLM/embedding pipeline, visualizes risk on a live dashboard, and takes safe, human-approved response actions — up to and including banning an attacking IP.

**Core loop:** `Watch → Scan → Explain (AI) → Show (Dashboard) → Act (auto-response)`

**Target user:** indie developers, small teams, and homelab/self-hosted operators who want enterprise-style security monitoring without a SOC.

---

## 2. Goals & Non-Goals

### Goals
- Detect hardcoded secrets, vulnerable dependencies, unauthorized file changes, and suspicious auth/log activity in near real time.
- Explain every finding in plain English with a suggested fix, cheaply and locally (no per-finding cloud LLM cost).
- Detect live attacks against a monitored server/container and alert immediately.
- Support IP banning as a manual-confirm action from the dashboard (never fully automatic for destructive network actions... except where explicitly scoped below as an opt-in auto-response, see §9).
- Run as a single `docker-compose up` for local/dev use, and as a small sidecar container attached to a user's server for production log monitoring.

### Non-Goals (v0.1)
- Not a full SIEM/XDR replacement.
- Not distributed/multi-tenant SaaS in this phase (single-admin MVP; multi-tenant is a v2 concern).
- No kernel-level EDR, no deep packet inspection beyond basic local pattern flags.
- No auto-remediation of code (no auto-patching dependencies, no auto-editing files).

---

## 3. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend API | Python 3.11 + FastAPI | async, WebSocket support built in |
| Event storage | SQLite | file-based, zero-ops for MVP; swappable to Postgres later |
| Real-time/state cache | Redis | in-memory fallback (Python dict + asyncio locks) if Redis unreachable |
| Frontend | React + Vite + Tailwind + Recharts | SPA, WebSocket client for live feed |
| AI explanation | Ollama (local LLM, e.g. `llama3.2` or `qwen2.5:3b`) | plain-English explain/fix suggestions, cached |
| Anomaly/attack detection | Local embeddings + Isolation Forest | see §8 — replaces heavy LLM inference for log-line classification |
| File watching | `watchdog` (Python) | recursive directory monitoring |
| Packet/log parsing | Scapy (optional) + log regex parsers | sandboxed; mocked if no root/capabilities available |
| Auth | JWT, single admin user | bcrypt-hashed password, short-lived access + refresh token |
| Background jobs | `asyncio` tasks / `APScheduler` | scan scheduling, embedding batch jobs |
| Containerization | Docker + docker-compose | one-command spin-up; separate "sentinel-agent" image for user servers |

---

## 4. High-Level Architecture

```
                        ┌─────────────────────────────┐
                        │        React Frontend       │
                        │  (dashboard, live feed, WS) │
                        └──────────────┬───────────────┘
                                       │ REST + WebSocket
                        ┌──────────────▼───────────────┐
                        │        FastAPI Backend        │
                        │  ┌─────────────────────────┐  │
                        │  │  Scan Orchestrator       │  │
                        │  ├─────────────────────────┤  │
                        │  │  Fusion / Scoring Engine │  │
                        │  ├─────────────────────────┤  │
                        │  │  AI Explainer (Ollama)   │  │
                        │  ├─────────────────────────┤  │
                        │  │  Anomaly Engine          │  │
                        │  │  (MiniLM embed + IForest)│  │
                        │  ├─────────────────────────┤  │
                        │  │  Auto-Response Engine    │  │
                        │  ├─────────────────────────┤  │
                        │  │  Audit Log               │  │
                        │  └─────────────────────────┘  │
                        └───┬───────┬────────┬──────────┘
                            │       │        │
                 ┌──────────▼──┐ ┌──▼───┐ ┌──▼────────────┐
                 │  SQLite DB  │ │Redis │ │ Ollama runtime │
                 └─────────────┘ └──────┘ └────────────────┘

     Monitored targets (local or remote):
     ┌───────────────────────────────┐     ┌──────────────────────────────┐
     │  Local folder/repo (Modules   │     │  Sentinel-Agent container     │
     │  1 & 2: scanner + FIM)        │     │  (deployed on user's server;  │
     └───────────────────────────────┘     │  ships logs/events to core    │
                                            │  backend over authenticated   │
                                            │  HTTPS/WebSocket)              │
                                            └──────────────────────────────┘
```

---

## 5. Modules

### Module 1 — Code & Secret Scanner
- Recursive scan of a target folder/repo.
- Secret detection: regex rule set (AWS keys, GitHub tokens, private keys, generic API key patterns, DB connection strings) + Shannon entropy scoring on candidate strings to catch high-entropy tokens regex misses.
- Dependency scan: parse `requirements.txt` / `package.json` (and lockfiles where present), query OSV.dev API for known CVEs per package/version, cache results (package+version → CVE list) to avoid re-querying.
- Output: structured finding `{id, file, line, type, severity, snippet, rule_id, detected_at}`.

### Module 2 — File Integrity Monitor (FIM)
- `watchdog` observer on configured directories.
- SHA256 baseline hash per file on first scan; store in SQLite.
- On any modify/create/delete/rename event: recompute hash, compare to baseline, flag if changed on a "critical files" list (configurable glob patterns, e.g. `*.env`, `/etc/passwd`-equivalents, config files).
- Debounce rapid successive writes (e.g. editor autosave) with a short window before flagging.

### Module 3 — Network/Log Monitor
- Auth/system log parser: tails configured log files (or `journalctl`/Windows Event Log equivalent where available), regex-matches for failed logins, repeated auth failures from same source within a time window (brute-force heuristic), privilege escalation keywords.
- Optional packet sniffer (Scapy): flags port-scan-like behavior (many distinct ports hit from one source in a short window). Requires elevated privileges; if unavailable in the runtime environment, this submodule runs in **mock mode** — clearly labeled sample data instead of live capture.
- Feeds structured log events into the Anomaly Engine (§8) rather than only regex — this is what upgrades "basic log parsing" into actual attack detection.

### Module 4 — AI Explainer Engine
- Every finding from Modules 1–3 (and anomaly alerts from the Anomaly Engine) is sent to a local Ollama model with a structured prompt.
- Response schema: `{explanation, severity_justification, suggested_fix}`.
- Cache key: hash of `(finding_type, normalized_snippet/log_template, severity)` → cached explanation, so identical/near-identical findings are not re-processed. Cache stored in SQLite (or Redis with SQLite fallback for persistence).
- Ollama model is configurable per deployment (Settings page), defaulting to a small instruction-tuned model suitable for CPU inference.

### Module 5 — Fusion / Scoring Engine
- Aggregates all open findings into one Security Score (0–100, 100 = best).
- Score = weighted deduction model: each finding subtracts `severity_weight × category_weight`, floor at 0, with diminishing-returns damping so 50 low-severity findings don't over-punish relative to 1 critical.
- Correlation boost: findings within a configurable time window (default 5 min) that touch related entities (e.g. a secret-leak finding + a failed-login spike from a related service) get their combined severity escalated by one tier, and are linked as a "correlated incident" in the UI.

### Module 6 — Dashboard (React)
- **Login** — JWT auth screen.
- **Overview** — security score gauge, findings-by-severity chart (Recharts), recent activity feed, live attack indicator.
- **Findings list** — filterable/sortable table (by severity, type, status, date); click-through to detail view with AI explanation + suggested fix + "Recommended Action" button.
- **Live feed** — WebSocket-driven stream of new findings/alerts as detected, no page refresh.
- **Attacks / Live Monitoring** — dedicated view showing active/recent detected attack events (see §7, §8), source IPs, confidence scores, and ban status.
- **Settings** — scan targets, scan frequency, Ollama model selection, critical-file patterns, anomaly-detection sensitivity, IP allow/deny list management.

### Module 7 — Auto-Response (safe defaults + scoped exceptions)
- On critical finding: write to audit trail (always, automatic), push dashboard alert (always, automatic), optionally send email via a mock/test email service (real SMTP only if the user supplies credentials).
- **No destructive auto-actions on code or the host filesystem** — no auto-patching, no auto-editing, no auto-deleting.
- **IP banning is the one exception, and it is opt-in and scoped, not blanket-automatic:**
  - Default mode: detected attacker IP surfaces a **"Ban IP" recommended action** button requiring manual confirm, per the original safe-defaults design.
  - Opt-in mode (explicit setting, off by default): for a specific monitored target/container, the user can enable **auto-ban on high-confidence attack detections** (Isolation Forest anomaly score above a configured threshold, sustained over N events). When enabled, the ban is executed automatically, logged immutably to the audit trail with full justification (score, log window, rule/model version), and reversible via a one-click "unban" in the dashboard.
  - Banning itself is implemented at the network edge closest to the monitored target: for the sentinel-agent container model (§9), this means an `iptables`/nftables rule (or reverse-proxy/WAF deny rule) scoped to that container's network namespace — never a host-wide firewall change from the core backend.

### Module 8 — Audit Log
- Immutable, append-only log (SQLite table with no UPDATE/DELETE application-level access; writes are insert-only) of every finding and every action: created, viewed, dismissed, fix-applied, ban-executed, ban-reversed.
- Each entry: `{id, timestamp, actor (user/system), action, target_finding_id, details_json, hash_of_previous_entry}` — chained hash so tampering is at least detectable, blockchain-lite style, without the overhead of an actual chain.

---

## 6. New Feature Set (this revision)

These extend the original 8 modules and are the primary delta for this spec revision.

### 6.1 Live Monitoring
- Real-time dashboard view (WebSocket-backed) showing current state of all monitored targets: local folders/repos AND remote sentinel-agent containers.
- Status per target: last scan time, open findings count, current security score, live event throughput (events/sec), connection health.

### 6.2 Loophole & Endpoint Detection
- Lightweight active/passive discovery of exposed endpoints on a monitored server: open ports, exposed HTTP routes discovered via log traffic (not active brute-force probing — passive observation only, to stay non-destructive and legal-by-default), default/debug endpoints left enabled (e.g. `/admin`, `/.env`, `/actuator`, `/debug`), and misconfigurations (permissive CORS, missing auth headers observed in traffic).
- Findings reported through the same pipeline as Modules 1–3: structured finding → AI Explainer → Fusion Engine → Dashboard.
- This is explicitly **detection and reporting only** — no active exploitation, no automated pentesting against third-party infrastructure. Scope is limited to servers/containers the user owns and has explicitly registered as a monitored target (enforced via the agent's own auth token, which is scoped to one deployment target).

### 6.3 Attack Detection & Alerting
- When the Anomaly Engine (§8, below) classifies a sequence of log events as attack-like (brute force, credential stuffing, scanning, injection attempt patterns in request logs), an **Attack Event** is created: `{source_ip, target, attack_type_guess, confidence, first_seen, last_seen, sample_log_lines}`.
- Attack Events are surfaced immediately via WebSocket to the Live Monitoring view and trigger the Auto-Response pipeline (§7) at critical severity by default.

### 6.4 IP Banning
- See Module 7 above for the confirm-by-default / opt-in-auto-ban-on-high-confidence design.
- Ban implementation detail: agent-side enforcement (container network namespace), not core-backend-side, so a compromised or misconfigured core backend can never reach out and firewall an arbitrary host. The agent exposes a narrow local action API (`POST /agent/actions/ban {ip, ttl}`) that only the core backend (authenticated) can call, and only for IPs it has itself flagged.
- Bans are TTL-based by default (e.g. 24h) with manual "make permanent" or "unban early" controls — avoids permanently locking out a false-positive (e.g. shared NAT IP, dynamic residential IP later reassigned).

### 6.5 Sentinel-Agent Container (user-deployed monitoring sidecar)
- A separate, minimal Docker image (`vibesentinel/agent`) the user runs alongside their own server/app.
- Responsibilities: tail configured log sources (app logs, nginx/apache access logs, auth logs) inside the user's environment, run the lightweight embedding + Isolation Forest pipeline **locally in the agent** (so raw logs never have to leave the user's infra — only structured findings/scores are shipped to the core backend), and expose the local ban-action API described in 6.4.
- Communicates to the core VibeSentinel backend over authenticated HTTPS/WebSocket (agent registers with a per-deployment token issued from the dashboard Settings page).
- This is the mechanism that makes "users can run their servers in a container and we see the logs for detecting attacks" work without VibeSentinel needing raw log access to third-party infrastructure — a real trust/privacy improvement over shipping raw logs to a central service.

---

## 7. Anomaly Detection Pipeline (replaces heavy-LLM-per-log-line approach)

Rather than sending every log line to Ollama (too slow/expensive for high-volume log streams), attack detection uses a **local, ultra-lightweight embedding + classical ML** pipeline:

1. **Log normalization** — raw log line → template (strip IPs/timestamps/ids into placeholders, similar to Drain/log-parsing approaches) so structurally identical events cluster together.
2. **Embedding** — normalized template passed through a compact sentence-embedding model:
   - Primary: `all-MiniLM-L6-v2` (~22MB) via ONNX Runtime (CPU-friendly, sub-millisecond inference per line at batch).
   - Alternative/upgrade path: `bge-small-en-v1.5` (~130MB) if higher embedding quality is needed and the extra footprint is acceptable.
3. **Anomaly scoring** — embeddings fed into an **Isolation Forest** (scikit-learn), trained per-target on a rolling window of "normal" traffic for that specific server/log source. Isolation Forest is chosen over a heavier classifier because: no labeled attack data required (unsupervised), fast to retrain incrementally as normal traffic drifts, cheap enough to run continuously on a small VM/container.
4. **Thresholding & escalation** — anomaly score above configured threshold → candidate Attack Event; sustained/clustered anomalies from the same source IP within a time window → confidence escalates, feeding Module 7's auto-ban opt-in path.
5. **AI Explainer hook** — only *escalated* Attack Events (not every anomalous line) get sent to Ollama for a plain-English summary — keeps LLM load proportional to actual incidents, not raw log volume.
6. **Model lifecycle** — per-target Isolation Forest models retrained on a schedule (e.g. nightly) or on-demand from Settings; old models versioned so a bad retrain can be rolled back.

This pipeline is the technical core of "detect hacker attacks and report them" and is what makes running this against a live, noisy production log stream computationally realistic on modest hardware.

---

## 8. Data Model (SQLite, MVP)

Key tables (fields abbreviated):

- `users(id, username, password_hash, created_at)`
- `targets(id, name, type[local_folder|agent], path_or_agent_id, scan_frequency, config_json)`
- `findings(id, target_id, source_module, type, severity, file, line, snippet, rule_id, status, created_at)`
- `explanations(finding_hash, explanation, severity_justification, suggested_fix, model_used, created_at)` — cache table
- `file_baselines(target_id, path, sha256, updated_at)`
- `log_events(id, target_id, raw_line, template, embedding_ref, anomaly_score, created_at)`
- `attack_events(id, target_id, source_ip, attack_type_guess, confidence, first_seen, last_seen, status)`
- `bans(id, target_id, source_ip, mode[manual|auto], ttl_expires_at, reversed_at, justification_json)`
- `audit_log(id, timestamp, actor, action, target_finding_id, details_json, prev_hash, entry_hash)`

---

## 9. API Surface (indicative)

```
POST   /auth/login
POST   /auth/refresh

GET    /targets
POST   /targets
POST   /targets/{id}/scan            # trigger manual scan

GET    /findings?severity=&status=&sort=
GET    /findings/{id}
POST   /findings/{id}/dismiss
POST   /findings/{id}/apply-fix      # manual-confirm only

GET    /score                        # current fused security score

GET    /attacks                      # attack events feed
POST   /attacks/{id}/ban             # manual confirm
POST   /attacks/{id}/unban

GET    /audit-log

WS     /ws/live                      # findings + attack events + score deltas

# Agent-facing (called by sentinel-agent, agent-token authenticated)
POST   /agent/register
POST   /agent/events/batch           # structured findings/scores, not raw logs
POST   /agent/heartbeat

# Agent-local (called by core backend, scoped to one agent)
POST   /agent/actions/ban {ip, ttl}  # exposed BY the agent, not the core
```

---

## 10. Security & Trust Boundaries
- Raw logs stay on the user's infrastructure; only normalized findings, embeddings-derived scores, and attack events cross the network to the core backend.
- Agent ↔ core auth via per-deployment scoped token; core cannot address an agent it didn't issue a token to, and cannot ban on a target it didn't itself flag.
- Ban execution is agent-local (network-namespace scoped), never a host-wide or core-backend-initiated firewall change.
- JWT access tokens short-lived; refresh token rotation; single-admin model for MVP (multi-user RBAC is a v2 item).
- Endpoint/loophole detection (6.2) is passive-observation only — no active exploitation or third-party scanning, keeping the feature legal-by-default for self-hosted use.

---

## 11. Non-Functional Requirements
- Clean project structure: `/backend`, `/frontend`, `/agent`, `/docs`.
- `README.md` with setup instructions, including local Ollama install/run steps.
- `.env.example` covering all config (JWT secret, Ollama host/model, Redis URL, OSV API settings, agent token signing key).
- `pytest` coverage for scanner logic (secret detection, entropy scoring, OSV lookups mocked) and for the anomaly pipeline (embedding → IForest scoring on fixture log sets).
- `docker-compose.yml` bringing up backend + frontend + Redis + Ollama in one command; separate `docker-compose.agent.yml` (or standalone `Dockerfile.agent`) for the user-deployed sentinel-agent.

---

## 12. Build Phasing (recommended order)

1. **Foundation** — FastAPI skeleton, SQLite models, JWT auth, docker-compose baseline.
2. **Module 1 + 2** — secret scanner + FIM, since these have no ML dependency and validate the finding pipeline end to end.
3. **Module 4 + 5** — AI explainer (Ollama) + fusion scoring, wired to Module 1/2 output.
4. **Module 6** — dashboard, so there's a visible product loop early.
5. **Module 3 + Anomaly Pipeline (§7)** — log monitor, MiniLM embedding, Isolation Forest, attack events.
6. **Module 7 + IP ban path** — auto-response, manual-confirm ban, opt-in auto-ban.
7. **Sentinel-Agent container (6.5)** — extract the log-tailing + embedding + local-ban pieces into the standalone agent image, wire agent↔core protocol.
8. **Module 8 hardening** — chained-hash audit log, retro-fill audit entries for everything above.
9. **Loophole/endpoint detection (6.2)** — layered on top of the log/traffic data already flowing through the agent.

## 13. Explicitly Mocked / Environment-Dependent Pieces (flag up front)
- Scapy packet sniffing: requires elevated privileges; falls back to labeled sample data if unavailable.
- Real SMTP email: mocked/test email service unless the user supplies real credentials.
- OSV.dev CVE lookups: require outbound network access at scan time; degrade to "unknown, network unavailable" rather than failing the scan.
- Ollama: requires the user to install/run Ollama locally with a pulled model; backend should detect unavailability and surface a clear "AI explainer offline" state rather than blocking the rest of the pipeline.
