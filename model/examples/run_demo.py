"""Minimal runnable example (spec §4 step 6): parse -> embed -> train -> detect.

Usage: python examples/run_demo.py
Requires artifacts/all-MiniLM-L6-v2/ — run scripts/export_onnx_model.py first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vibesentinel_model.embedder import ModelArtifactsMissing
from vibesentinel_model.pipeline import LogPipeline

from synthetic_logs import generate_dataset


def main() -> None:
    data = generate_dataset()

    try:
        pipeline = LogPipeline(target_id="demo-target")
    except ModelArtifactsMissing as exc:
        print(f"[!] {exc}")
        sys.exit(1)

    print(f"training on {len(data['baseline'])} baseline lines...")
    pipeline.train(data["baseline"])
    print(f"malformed lines during training: {pipeline.malformed_line_count}")

    for label in ("normal_eval", "sqli", "traversal", "xss"):
        print(f"\n--- {label} ---")
        results = pipeline.detect(data[label])
        for r in results:
            tag = "ANOMALY" if r.flag == -1 else "normal "
            print(f"  [{tag}] severity={r.severity_score:.2f}  {r.template[:80]}")


if __name__ == "__main__":
    main()
