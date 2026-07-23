# Model performance & live detection stats

How the anomaly model actually performs — both the offline eval on real datasets
and a live end-to-end run through the hosted environment platform (the pivot
described in `CLAUDE.md`).

The detection stack is fully local, no LLM: **Drain3** (log→template) →
**MiniLM-L6-v2 via ONNX** (template→embedding) → **Isolation Forest** (per-target
anomaly score), combined with a **URL-decode-aware signature pre-filter** for
known attack payloads. Full design + tuning history: `model/README.md`.

---

## 1. Offline eval (shipped dataset baselines)

Per-source Isolation Forest, `contamination=0.05`, Drain3 `sim_th=0.4`, no
template dedup, 3000-line baseline. `flagged` = raw IsolationForest `-1` label
combined with the signature pre-filter (the primary metric). Reproduce with
`python model/scripts/train_baseline.py --with-csic`.

| Source | Normal false-positive rate | Attack detection rate |
|---|---|---|
| Apache | 3% | 64% |
| Linux | 3% | 85% |
| SSH | 2% | 100% |
| Nginx | 4% | 100% |
| CSIC2010 (real HTTP attack labels) | 2% | 20% — payload-signature ceiling, see below |

**Why CSIC2010 is lower:** its attack set includes parameter-tampering and
business-logic abuse (e.g. `precio=85` → `precio=1`) that is byte-for-byte a
normal request — no log-line anomaly detector or regex catches that class; it
needs application-level field validation. The behavioral attacks (brute force,
scanning, volume drift) are exactly what the Isolation Forest handles well, and
payload attacks (SQLi/XSS/traversal/cmdi) are what the signature layer covers —
which is what the live test below exercises.

---

## 2. Live detection through the platform

End-to-end run against the real pipeline as wired into the hosted core: a demo
server logging nginx-combined access lines in the **server terminal**, driven by
`/opt/traffic.py` from the **tests terminal**. The monitor seeds from the shipped
`nginx` model and taps the server terminal's live output. Reproduce with the
"Demo project" steps below.

**Run: 40 requests (31 normal, 9 attack) mixed randomly, ~1-in-5 malicious.**

| Metric | Result |
|---|---|
| Attack requests sent | 9 |
| Attack requests flagged | **9 (100% recall)** |
| Normal requests sent | 31 |
| False-positive alerts on normal traffic | **0** |
| Signatures fired | recon_probe ×4, xss ×3, traversal ×1, sqli ×1 |

```json
{"attacks_sent": 9, "normal_sent": 31, "attack_alerts": 9,
 "by_signature": {"recon_probe": 4, "xss": 3, "traversal": 1, "sqli": 1},
 "anomaly_fp": 0, "recall": 1.0}
```

Notes:
- The single command-injection payload (`; cat /etc/shadow`) was caught but
  categorized `traversal` — the `/etc/shadow` traversal pattern matches before the
  cmdi pattern in `signatures.py`'s ordered list. Still flagged as an attack, so
  recall is unaffected; it's a label-ordering detail, not a miss.
- **Zero false positives** is the payoff of two guards added in this release: a
  shell-prompt filter (a PTY tap sees the interactive shell, not just server
  output) and a **warmup window** — for the first 25 scored lines the monitor
  suppresses ML-only anomalies (a seed model flags unseen-but-benign templates
  until it has seen enough of the new target's own traffic) while still firing on
  any signature attack from request #1. Before warmup suppression the same run
  produced 2–3 cold-start FPs (server banner + first request).

---

## 3. Demo project — reproduce it yourself

Every environment ships with the demo assets, so any project is a demo project:

1. Start the core: `uvicorn vibesentinel_core.main:app --port 8000` (from `/backend`)
2. Open the dashboard (served on the same port) → create a project — note its auto access id.
3. **Server terminal:** `python3 /opt/demo_server.py`
4. **Tests terminal:** `python3 /opt/traffic.py` (or `--forever` for continuous)
5. Watch the live alert feed: every `[attack:*]` line the generator sends should
   raise an `attack` alert; normal traffic stays quiet after warmup.

---

_Generated 2026-07-24 from `model/README.md` eval + a live platform run
(`backend/vibesentinel_core`). Re-run the live numbers any time via the demo
project above._
