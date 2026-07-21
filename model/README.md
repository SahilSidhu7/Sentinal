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
scripts/
  export_onnx_model.py   one-time model export (run before first use)
examples/
  synthetic_logs.py       normal traffic + SQLi/traversal/XSS samples
  run_demo.py              runs the full pipeline end-to-end, prints results
tests/
  test_pipeline.py
```

## Setup

```
pip install -r requirements.txt
python scripts/export_onnx_model.py     # downloads + exports MiniLM to ./artifacts/
python examples/run_demo.py             # sanity check on synthetic logs
```

## Contract other teams depend on (keep stable — see spec §8)

```python
from vibesentinel_model.pipeline import LogPipeline

pipeline = LogPipeline(target_id="my-target")
pipeline.train(baseline_log_lines: list[str]) -> None
results = pipeline.detect(log_lines: list[str]) -> list[DetectionResult]
# DetectionResult: template: str, flag: int (-1 anomalous / 1 normal), severity_score: float (0-1)
```

`/cli` and `/backend` import this package directly (no HTTP boundary). Don't change the `train`/`detect` signatures or `DetectionResult` fields without flagging it in `/docs` — both other teams build against this shape.

## Constraints (non-negotiable, see spec §4)

- No PyTorch, no full `transformers`. ONNX Runtime + a lightweight tokenizer only.
- Batch processing, not per-line — `detect()`/`train()` take lists.
- Malformed/unparseable lines are counted and skipped, never raise out of a batch.
- Memory budget: whole pipeline (Drain3 store + ONNX session + one loaded IsolationForest) under 150MB resident.
