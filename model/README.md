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
  signatures.py      known-payload regex pre-filter (sqli/xss/traversal/cmdi/recon_probe/
                      overflow/crlf), URL-decode aware — combined into detect() results
scripts/
  export_onnx_model.py   one-time model export (run before first use)
  prepare_datasets.py     extracts datasets/*.tar.gz (loghub)
  fetch_nginx_dataset.py   pulls recent real nginx logs from secrepo.com
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
  test_signatures.py
```

## Setup

```
pip install -r requirements.txt
python scripts/export_onnx_model.py     # downloads + exports MiniLM to ./artifacts/ (~90MB, gitignored — not ours to ship)
python examples/run_demo.py             # sanity check on synthetic logs
```

`artifacts/models/*.joblib` + `artifacts/drain3_state/*.bin` (the 5 dataset-trained baselines from the eval table below) **are** committed — a fresh clone can seed a new target's detection from one of them immediately via `LogPipeline.seed_from_pretrained("nginx")` (see `/cli`'s `--seed-model` option) without waiting to export the ONNX model or accumulate its own baseline first. You still need the ONNX export step above to run `detect()`/`train()` at all — the shipped `.joblib` files are the Isolation Forests, not the embedder.

## Continuous improvement (seed -> adapt)

A target doesn't stay pinned to its seed model. `/cli`'s `run` loop accumulates the target's own normal-flagged traffic and periodically calls `train()` again on it (`--retrain-every`, default 500 lines) — each retrain versions the previous model (`AnomalyModel._persist`) rather than discarding it, so detection keeps adapting to what this specific target's real traffic actually looks like instead of staying frozen on someone else's dataset.

## Training on real data

`datasets/` holds real logs: loghub Apache/Linux/SSH (regex-derived weak labels, eval-only), Nginx (real secrepo.com traffic, CC-BY 4.0), and CSIC 2010 (real ground-truth `norm`/`anom` labels per request) — see `datasets/SOURCES.md` for provenance. `scripts/train_baseline.py` trains a per-source Isolation Forest and evaluates it:

```
python scripts/fetch_nginx_dataset.py    # once, pulls real nginx logs
python scripts/train_baseline.py --with-csic
```

Current numbers (contamination=0.05, Drain3 `sim_th=0.4`, no template dedup, 3000-line baseline; `flagged` is the raw IsolationForest `-1` label combined with `signatures.py`'s payload pre-filter — the primary metric, not `severity_score` alone):

| Source | Normal false-positive rate | Attack detection rate |
|---|---|---|
| Apache | 3% | 64% |
| Linux | 3% | 85% |
| SSH | 2% | 100% |
| Nginx | 4% | 100% |
| CSIC2010 | 2% | 20% (real ground truth, still a gap — see known limitation 2) |

**This is the config to keep.** History: an earlier pass deduped training to unique templates and tightened `sim_th` to 0.65 chasing higher SSH recall, which pushed FP up to 12/8/44% — much worse for a system where a false positive can end in banning a real user. Reverted: `LogPipeline.train()` no longer dedupes (density estimate benefits from knowing how often a template actually recurs in normal traffic), `sim_th` back to 0.4, `contamination` back to 0.05, baseline back to 3000 lines. `EscalationTracker.observe()` gates on the raw `flag` (contamination-calibrated) first, with `severity_score` as a secondary floor — gating on `severity_score` alone was the mechanism that let FP creep up in the tuning detour.

Three real bugs surfaced and fixed while chasing these numbers (worth knowing before trusting any future eval run's numbers at face value):
- **Apache's heuristic eval label was wrong, not the detector.** `heuristics.py`'s apache pattern never caught `cgi-bin/awstats`/`phpmyadmin` probing (a real, well-known exploit-scanning campaign present in that 2005-2006 dataset) — those lines were bucketed as "normal," so the detector correctly flagging them looked like a false-positive spike. Fixed the heuristic; apache's real FP is 3%, not the 8% an earlier run showed.
- **Signature payloads are routinely URL-encoded** (`%27%3B+DROP+TABLE` for `'; DROP TABLE`, sometimes double-encoded: `%253C` → `%3C` → `<`). `signatures.py` didn't decode before matching, so it barely helped CSIC2010 (2% recall) — fixed with `unquote_plus` applied once and twice before matching.
- **A shared `random.Random` across all 5 sources made every source's eval sample depend on every *other* source's data.** Fixing apache's heuristic changed how many random calls its shuffle consumed, which silently reshuffled SSH's sample and swung its reported recall from 46% to 9% with zero actual change to SSH. `train_baseline.py` now seeds a fresh `random.Random(f"{SEED}-{target_id}")` per source — each source's numbers are now independent of what other sources' data looks like.

### Known limitation 1: per-line false-positive rate on Apache/Linux/SSH/Nginx is real, not zero

These logs have genuinely heterogeneous "normal" traffic (mixed subsystems, rare one-off messages a fixed-size baseline never sees) — the 2-4% FP above is the best tradeoff found, not zero.

**This is why `escalation.py` exists and why nothing in this package should gate a destructive action off a single flagged line.** `EscalationTracker` requires `MIN_EVENTS_TO_ESCALATE` (default 4) anomalous hits from the *same source IP* inside a 5-minute window before it even returns an `AttackEvent`, and even reaching the `ban_ip` tier (10+ sustained events, ≥0.85 confidence) is a *recommendation* — per spec Module 7, ban execution itself stays manual-confirm by default regardless of what this package outputs, and any target that opts into auto-ban gets TTL-based, reversible bans. At a 2-4% per-line FP rate, the odds of one legitimate IP racking up 10 sustained flagged events in 5 minutes purely by chance are low; per-line noise gets absorbed before it ever reaches a human, let alone an action.

If a specific target's false-positive rate matters more than these defaults (e.g. tighter compliance environment), calibrate `contamination` and `EscalationTracker`'s thresholds per-target — this should be exposed as the "anomaly-detection sensitivity" Settings knob in spec §3 Module 6, not hardcoded.

### Known limitation 2: CSIC 2010 (real SQLi/XSS/traversal traffic) — signature layer closed most of the gap, not all of it

CSIC2010's ground truth is real (`norm`/`anom` per HTTP request, not a regex proxy). Original diagnosis: mean-pooled sentence embeddings of a full request line dilute a short injected payload (`<script>alert(1)</script>`) inside otherwise-ordinary form-field text — the whole-line embedding ends up dominated by the ordinary tokens, so the ML layer alone stayed near 0% recall regardless of threshold. Fix: `signatures.py`, a fast regex pre-filter (SQLi, XSS, path traversal, command injection, plus recon-probe paths, overflow/fuzz strings, CRLF injection — 7 categories, URL-decode aware) whose hits force `flag=-1` in `pipeline.detect()`, independent of the ML score. This took CSIC2010 recall from 0% → 20% without moving its FP (2%).

**Recall ceiling that remains, and why:** CSIC2010's attack set also includes buffer overflow, parameter tampering, and files-disclosure requests that don't reduce to a payload signature — parameter tampering in particular (e.g. changing `precio=85` to `precio=1`) is syntactically identical to a normal request; nothing about the string itself is anomalous, only the business-logic value is wrong. No regex or generic anomaly-embedding approach catches that class — it needs application-level validation (expected-range/type checking on specific fields), which is out of scope for a log-line anomaly detector. `scripts/csic_dataset.py` (verified against the dataset's published 36k/25k stats) stays in the repo, not wired into `train_baseline.py`'s default run (`--with-csic` to include it).

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
