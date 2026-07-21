# /model — Anomaly Detection & Training (Team C)

Branch: `model` · Spec: `docs/SPEC.md` §4, §8

Owns the local, LLM-free attack-detection pipeline: raw log line → template → embedding → anomaly score. No network calls, no GPU, <150MB resident per target.

## Pipeline

```
raw log line
  -> log_parser.py   (Drain3: strip IPs/timestamps/UUIDs/IDs -> template)
  -> embedder.py      (ONNX Runtime + all-MiniLM-L6-v2 -> vector)
  -> anomaly.py        (Isolation Forest: train() / detect())
  -> pipeline.py       (batches the above, handles malformed lines)
```

## Layout

```
vibesentinel_model/
  log_parser.py    Drain3 wrapper, template extraction, persistence
  embedder.py       ONNX MiniLM loader + batch embedding
  anomaly.py        IsolationForest train/detect, joblib persistence
  pipeline.py       LogPipeline: batch ingest -> templates -> vectors -> scores
  escalation.py     EscalationTracker: sustained per-source-IP gating + response ladder
scripts/
  export_onnx_model.py   one-time model export (run before first use)
  prepare_datasets.py     extracts datasets/*.tar.gz (loghub)
  csic_dataset.py          extracts + reconstructs CSIC2010 request lines (real labels)
  heuristics.py            weak eval-only attack labels (never fed into training)
  train_baseline.py       real train+eval on datasets/ (--with-csic for CSIC2010)
examples/
  synthetic_logs.py       normal traffic + SQLi/traversal/XSS samples
  run_demo.py              runs the full pipeline end-to-end, prints results
datasets/
  SOURCES.md               provenance + candidate datasets to add next
tests/
  test_pipeline.py
  test_escalation.py
```

## Setup

```
pip install -r requirements.txt
python scripts/export_onnx_model.py     # downloads + exports MiniLM to ./artifacts/
python examples/run_demo.py             # sanity check on synthetic logs
```

## Training on real data

`datasets/` holds real logs: loghub Apache/Linux/SSH (regex-derived weak labels, eval-only) and CSIC 2010 (real ground-truth `norm`/`anom` labels per request) — see `datasets/SOURCES.md` for provenance. `scripts/train_baseline.py` trains a per-source Isolation Forest and evaluates it:

```
python scripts/train_baseline.py
```

Current numbers (contamination=0.05, Drain3 `sim_th=0.4`, no template dedup — trains on raw-line template frequency; `flagged` below is the raw IsolationForest `-1` label, the primary metric, not `severity_score`):

| Source | Normal false-positive rate | Attack detection rate |
|---|---|---|
| Apache | 2% | 86% |
| Linux | 4% | 82% |
| SSH | 4% | 46% |
| CSIC2010 | 3% | 0% (no real separation — see known limitation below) |

**This is the config to keep.** History: an earlier pass deduped training to unique templates and tightened `sim_th` to 0.65 chasing higher SSH recall, which pushed FP up to 12/8/44% — much worse for a system where a false positive can end in banning a real user. Reverted: `LogPipeline.train()` no longer dedupes (density estimate benefits from knowing how often a template actually recurs in normal traffic), `sim_th` back to 0.4, `contamination` back to 0.05, baseline back to 3000 lines. `EscalationTracker.observe()` gates on the raw `flag` (contamination-calibrated) first, with `severity_score` as a secondary floor — gating on `severity_score` alone was the mechanism that let FP creep up in the tuning detour.

### Known limitation 1: per-line false-positive rate on Apache/Linux/SSH is real, not zero

These logs have genuinely heterogeneous "normal" traffic (mixed subsystems, rare one-off messages a fixed-size baseline never sees) — the 2-4% FP above is the best tradeoff found, not zero. SSH's lower recall (46%) is the cost of keeping its FP low: its brute-force traffic and a chunk of its legitimate traffic both reduce to short, generic auth-log templates that sit close together in embedding space, so tightening further to catch more attacks reliably drags normal traffic along with it.

**This is why `escalation.py` exists and why nothing in this package should gate a destructive action off a single flagged line.** `EscalationTracker` requires `MIN_EVENTS_TO_ESCALATE` (default 4) anomalous hits from the *same source IP* inside a 5-minute window before it even returns an `AttackEvent`, and even reaching the `ban_ip` tier (10+ sustained events, ≥0.85 confidence) is a *recommendation* — per spec Module 7, ban execution itself stays manual-confirm by default regardless of what this package outputs, and any target that opts into auto-ban gets TTL-based, reversible bans. At a 2-4% per-line FP rate, the odds of one legitimate IP racking up 10 sustained flagged events in 5 minutes purely by chance are low; per-line noise gets absorbed before it ever reaches a human, let alone an action.

If a specific target's false-positive rate matters more than these defaults (e.g. tighter compliance environment), calibrate `contamination` and `EscalationTracker`'s thresholds per-target — this should be exposed as the "anomaly-detection sensitivity" Settings knob in spec §3 Module 6, not hardcoded.

### Known limitation 2: CSIC 2010 (real SQLi/XSS/traversal traffic) doesn't separate with this approach

Unlike the other three, CSIC2010's ground truth is real (`norm`/`anom` per HTTP request, not a regex proxy) — and the pipeline still can't tell them apart: at this low-FP config it just flags almost nothing (0% recall alongside the 3% FP above); at higher-sensitivity configs tried earlier it flagged everything roughly equally (both land near 50-95%, i.e. close to random either way). Root cause, diagnosed not guessed: mean-pooled sentence embeddings of a full request line dilute a short injected payload (`<script>alert(1)</script>`) inside otherwise-ordinary form-field text (`login=`, `pwd=`, `remember=on`, real product names) — the whole-line embedding ends up dominated by the ordinary tokens. Tried: fixing Drain3's delimiter set (`&`/`?` weren't delimiters, so query strings were single blobs — fixed, `drain3_config.ini`) and a 20k-line baseline (3x the original) — neither closed the gap.

This isn't a call to abandon signature-style detection for SQLi/XSS/traversal — it's evidence that **this specific ML approach (structural/behavioral anomaly detection via IsolationForest) is the wrong tool for payload-content detection**, which is what CSIC2010 actually tests. Recommend a hybrid: keep a fast regex/signature pre-filter for known payload patterns (SQL keywords, script tags, traversal sequences — same philosophy as Module 1's scanner) ahead of or alongside this ML layer, which should focus on what it's actually good at: structural/behavioral drift (brute force, scanning, rare endpoints, volume anomalies) — exactly what Apache/Linux/SSH results above demonstrate it can do. `scripts/csic_dataset.py` (loader, verified against the dataset's published stats: 36k norm / 25k anom) stays in the repo for whoever picks up that signature-layer work; it's just not wired into `train_baseline.py`'s default run (`--with-csic` to include it).

## Response ladder (alternative to jumping straight to IP ban)

Auto-banning on a false positive has real cost — it can lock out a legitimate user. `escalation.py`'s `suggest_action()` implements a graduated ladder instead of a binary ban/no-ban:

| Confidence | Sustained events | Action |
|---|---|---|
| < 0.6 | any | `log_only` — no dashboard alert, just recorded |
| ≥ 0.6 | any | `flag_for_review` — dashboard alert, human decides, no automatic network action |
| ≥ 0.7 | ≥ 6 | `rate_limit_and_challenge` — throttle + CAPTCHA/JS challenge at the edge (reversible, no lockout) |
| ≥ 0.85 | ≥ 10 | `ban_ip` — still manual-confirm by default per spec Module 7; only auto-executes if the target has opted in |

`rate_limit_and_challenge` is the recommended default response for most detected attacks: it degrades an attacker's throughput and filters bots without permanently locking out a legitimate user on a false positive (a mis-flagged shared/dynamic IP just sees a CAPTCHA once, not a ban). Ban stays reserved for sustained, high-confidence, high-volume cases — implementing the actual rate-limit/CAPTCHA action is `/backend` Module 7 + `/cli`'s job; this package only produces the confidence + recommendation.

## Contract other teams depend on (keep stable — see spec §8)

```python
from vibesentinel_model import LogPipeline, EscalationTracker, extract_source_ip

pipeline = LogPipeline(target_id="my-target")
pipeline.train(baseline_log_lines: list[str], contamination: float = 0.05) -> None
results = pipeline.detect(log_lines: list[str]) -> list[DetectionResult]
# DetectionResult: template: str, flag: int (-1 anomalous / 1 normal), severity_score: float (0-1)

tracker = EscalationTracker()  # one per target, keep it alive across the log stream
for line, result in zip(log_lines, results):
    event = tracker.observe(extract_source_ip(line), result, timestamp=...)
    if event:  # AttackEvent: source_ip, confidence, event_count, suggested_action, ...
        ...    # hand off to /backend's Auto-Response pipeline
```

`/cli` and `/backend` import this package directly (no HTTP boundary). Don't change the `train`/`detect` signatures or `DetectionResult`/`AttackEvent` fields without flagging it in `/docs` — both other teams build against this shape.

## Constraints (non-negotiable, see spec §4)

- No PyTorch, no full `transformers`. ONNX Runtime + a lightweight tokenizer only.
- Batch processing, not per-line — `detect()`/`train()` take lists.
- Malformed/unparseable lines are counted and skipped, never raise out of a batch.
- Memory budget: whole pipeline (Drain3 store + ONNX session + one loaded IsolationForest) under 150MB resident.
