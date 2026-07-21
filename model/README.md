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
  prepare_datasets.py     extracts datasets/*.tar.gz
  heuristics.py            weak eval-only attack labels (never fed into training)
  train_baseline.py       real train+eval on the loghub datasets in datasets/
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

`datasets/` holds real loghub logs (Apache, Linux, SSH — see `datasets/SOURCES.md` for provenance). `scripts/train_baseline.py` trains a per-source Isolation Forest and evaluates it against regex-derived weak attack labels (eval-only — training itself stays unsupervised):

```
python scripts/train_baseline.py
```

Current numbers (contamination=0.03, Drain3 `sim_th=0.65`, severity gate 0.7):

| Source | Normal false-positive rate | Attack detection rate |
|---|---|---|
| Apache | 12% | 100% |
| Linux | 8% | 87% |
| SSH | 44% | 99% |

### Known limitation: per-line false-positive rate is real, not zero

These datasets have genuinely heterogeneous "normal" traffic (mixed subsystems, rare one-off messages a fixed-size baseline never sees) — no amount of threshold/baseline-size tuning drove Apache/SSH false positives near zero without also gutting recall (tried: baseline size 3k→15k, `contamination` 0.02→0.05, Drain3 `sim_th` 0.4→0.65 — see git history on the `model` branch for the full sweep). SSH is the hardest case: its "attack" traffic (brute-force) and a chunk of its legitimate traffic both reduce to short, generic auth-log templates that sit close together in embedding space.

**This is why `escalation.py` exists and why nothing in this package should gate a destructive action off a single flagged line.** `EscalationTracker` requires `MIN_EVENTS_TO_ESCALATE` (default 4) anomalous hits from the *same source IP* inside a 5-minute window before it even returns an `AttackEvent`, and `suggest_action()` only recommends `ban_ip` at sustained volume (10+ events) *and* high confidence (≥0.85). A rare-but-legitimate one-off message from a real user's IP won't repeat 4+ times in 5 minutes — that's the actual false-positive suppression mechanism, not per-line accuracy. See "Response ladder" below.

If a specific target's false-positive rate matters more than this default (e.g. tighter compliance environment), calibrate `contamination` and `EscalationTracker`'s thresholds per-target — this should be exposed as the "anomaly-detection sensitivity" Settings knob in spec §3 Module 6, not hardcoded.

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
pipeline.train(baseline_log_lines: list[str], contamination: float = 0.03) -> None
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
