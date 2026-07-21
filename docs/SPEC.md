# VibeSentinel — Product & Engineering Spec Sheet

Version: 0.2 (draft) · Status: Pre-build · Owner: Sahil Sidhu

## 1. Summary

Full-stack security monitoring platform for local machines / small self-hosted servers. Watches a target (folder, repo, container), scans for security issues, detects live attacks via a local Drain3 + ONNX embedding + Isolation Forest pipeline (**no LLM anywhere**), shows risk on a live dashboard, takes safe human-approved response actions (incl. opt-in auto IP-ban).

**Core loop:** `Watch → Scan → Detect → Show → Act`

**Non-goals (v0.1):** not a SIEM/XDR replacement, single-admin only, no kernel EDR, no auto-patching/auto-editing code.

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Backend API | Python 3.11 + FastAPI (async, WebSocket) |
| Storage | SQLite (Postgres-swappable later) + Redis (dict/asyncio fallback) |
| Frontend | React + Vite + Tailwind + Recharts |
| CLI / sentinel-agent | Python (Typer/Click) |
| Log parsing | Drain3 (template extraction: strip IPs/timestamps/UUIDs/IDs) |
| Embeddings | `all-MiniLM-L6-v2` via ONNX Runtime (no PyTorch/`transformers`) |
| Anomaly detection | Isolation Forest (scikit-learn), per-target |
| Explanations | Static rule-template metadata (no LLM) |
| File watching | `watchdog` |
| Packet/log capture | Scapy (optional, mock mode if unprivileged) + regex parsers |
| Auth | JWT, single admin, bcrypt |
| Containerization | Docker + docker-compose; separate `Dockerfile.agent` |

## 3. Modules

1. **Scanner** — secret detection (regex + Shannon entropy) and dependency CVE lookup (OSV.dev, cached), recursive over a target folder/repo.
2. **FIM** — `watchdog`-based baseline SHA256 hashing; flags changes to critical-file globs (`.env`, configs); debounced.
3. **Log/Network Monitor** — tails auth/access logs, regex brute-force/privesc heuristics, optional Scapy port-scan detection (mock if no privileges); feeds Anomaly Engine (§4).
4. **Explainer** — every finding/attack event resolves against a static rule-template table (`{explanation, severity_justification, suggested_fix}`), cached by `(type, normalized_snippet/template, severity)` hash.
5. **Fusion/Scoring** — Security Score 0–100, weighted deductions with diminishing returns; correlation boost escalates severity for related findings within a 5-min window.
6. **Dashboard** — login, overview (score, charts, live feed), findings table + detail view, live WebSocket feed, attacks view, settings.
7. **Auto-Response** — critical finding → audit write + dashboard alert (always). No destructive code/filesystem actions ever. IP ban: manual-confirm by default; opt-in auto-ban on sustained high-confidence anomaly score, executed **agent-side** (network-namespace scoped), TTL-based, reversible.
8. **Audit Log** — append-only, chained hash (`prev_hash`→`entry_hash`), every finding/action lifecycle event, no UPDATE/DELETE.
9. **Loophole/Endpoint Detection** — passive-only observation of exposed routes/default-debug endpoints/misconfig from traffic already flowing through the agent. No active probing of third-party infra.

## 4. Anomaly Detection Pipeline (local ML only)

Owned by `/model` team. CPU-only, must fit under **150MB** resident per target.

1. **Drain3** parses raw logs (Nginx/Apache/Syslog) into templates.
2. **ONNX MiniLM** embeds each template (batch, not per-line).
3. **Isolation Forest**: `train(target_id, embeddings)` fits on baseline "normal" traffic, saves `log_anomaly_model.joblib` (versioned). `detect(embeddings) -> (flag, severity_score)` where flag is -1/1 and severity_score is normalized 0–1.
4. Score above threshold → Attack Event; sustained same-source anomalies escalate confidence → feeds auto-ban path.
5. Malformed lines counted + skipped, never crash the batch.
6. Ships a runnable example: synthetic logs (normal + SQLi/traversal/XSS attacks) run through the full parse→embed→train→detect pipeline.

## 5. Data Model (SQLite, key tables)

`users`, `targets`, `findings`, `explanations` (cache), `file_baselines`, `log_events(raw_line, template, embedding_ref, anomaly_score)`, `attack_events(source_ip, attack_type_guess, confidence)`, `bans(mode, ttl_expires_at, reversed_at)`, `audit_log(prev_hash, entry_hash)`.

## 6. API Surface (indicative)

```
POST /auth/login, /auth/refresh
GET/POST /targets, POST /targets/{id}/scan
GET /findings, /findings/{id}, POST /findings/{id}/dismiss|apply-fix
GET /score
GET /attacks, POST /attacks/{id}/ban|unban
GET /audit-log
WS  /ws/live
# agent-facing (agent-token auth)
POST /agent/register, /agent/events/batch, /agent/heartbeat
# agent-local (core calls this ON the agent, scoped to one target)
POST /agent/actions/ban {ip, ttl}
```

## 7. Trust Boundaries

Raw logs never leave user infra — only templates/embeddings/scores cross the wire. Agent↔core auth via scoped per-deployment token. Ban execution is agent-local only (never core-initiated host-wide). Endpoint detection is passive-only.

## 8. Project Structure (4-team split)

```
/frontend   Team A — main React dashboard (Module 6), REST+WS client only.
/cli        Team B — sentinel-agent CLI: target reg, log tail, FIM, local ban API.
/model      Team C — Drain3 + ONNX embedding + Isolation Forest train/detect,
            joblib artifacts, synthetic-log example. Installable package
            imported by /cli and /backend — no HTTP boundary to /cli.
/dashboard  Team D — thin localhost-only status site served by /cli, for
            single-box operators without the full /backend running.
/backend    FastAPI core (Modules 1,2,5,7,8 + API in §6), imports /model.
/docs       Spec + ADRs.
```

Stable contract points: `/model.train()` / `/model.detect()` signatures; shared findings/attack-event JSON shape used by both `/backend` and `/cli` (so `/dashboard` can render either feed).

## 9. Build Order

1. Foundation (FastAPI, SQLite, JWT, docker-compose)
2. Scanner + FIM (Modules 1–2, no ML dep)
3. Explainer + Fusion (Modules 4–5)
4. Dashboard (Module 6)
5. Log Monitor + Anomaly Pipeline (§4) — testable standalone via synthetic example first
6. Auto-Response + IP ban (Module 7)
7. Sentinel-Agent CLI + `/dashboard` (§8)
8. Audit hardening (Module 8, chained hash)
9. Loophole/endpoint detection (Module 9)

## 10. Explicitly Mocked / Environment-Dependent

- Scapy sniffing: needs elevated privileges → labeled mock data if unavailable.
- SMTP email: mocked/test unless real credentials supplied.
- OSV.dev lookups: degrade to "unknown, network unavailable" if offline, never fail the scan.
