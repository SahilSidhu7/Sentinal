"""Train + sanity-eval per-source Isolation Forest models on the loghub datasets
in datasets/ (Apache, Linux, SSH). Real logs, not synthetic — see
datasets/SOURCES.md for provenance and the known gap (no HTTP-request-line
attack traffic in these three; that stays covered by examples/synthetic_logs.py).

Usage: python scripts/train_baseline.py [--baseline-size N] [--eval-size N]

Requires artifacts/all-MiniLM-L6-v2/ (run scripts/export_onnx_model.py first).
"""
import argparse
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="  [%(name)s] %(message)s")
logging.getLogger("drain3").setLevel(logging.WARNING)

from heuristics import is_suspicious
from prepare_datasets import ensure_extracted, iter_lines

from vibesentinel_model.embedder import ModelArtifactsMissing
from vibesentinel_model.pipeline import LogPipeline

SOURCES = ["apache", "linux", "ssh"]
SEED = 20260721


def split_lines(source: str, log_path: Path) -> tuple[list[str], list[str]]:
    normal, suspicious = [], []
    for line in iter_lines(log_path):
        (suspicious if is_suspicious(source, line) else normal).append(line)
    return normal, suspicious


def sample(lines: list[str], n: int, rng: random.Random) -> list[str]:
    if len(lines) <= n:
        return lines
    return rng.sample(lines, n)


SEVERITY_GATE = 0.7  # matches EscalationTracker's default — see vibesentinel_model/escalation.py


def report(label: str, results) -> None:
    if not results:
        print(f"    {label}: no lines")
        return
    above_gate = sum(1 for r in results if r.severity_score >= SEVERITY_GATE)
    avg_severity = sum(r.severity_score for r in results) / len(results)
    print(
        f"    {label}: n={len(results)} severity>={SEVERITY_GATE}={above_gate} "
        f"({above_gate / len(results):.0%}) avg_severity={avg_severity:.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-size", type=int, default=6000)
    parser.add_argument("--eval-size", type=int, default=400)
    parser.add_argument("--contamination", type=float, default=0.03)
    args = parser.parse_args()

    rng = random.Random(SEED)
    paths = ensure_extracted()

    for source in SOURCES:
        print(f"\n=== {source} ===")
        normal, suspicious = split_lines(source, paths[source])
        print(f"  total lines: normal={len(normal)} suspicious(heuristic)={len(suspicious)}")

        rng.shuffle(normal)
        baseline = normal[: args.baseline_size]
        normal_eval = normal[args.baseline_size : args.baseline_size + args.eval_size]
        attack_eval = sample(suspicious, args.eval_size, rng)

        if len(baseline) < 50:
            print(f"  [!] only {len(baseline)} normal lines, skipping (need >=50)")
            continue

        try:
            pipeline = LogPipeline(target_id=f"loghub-{source}")
        except ModelArtifactsMissing as exc:
            print(f"[!] {exc}")
            sys.exit(1)

        print(f"  training on {len(baseline)} baseline lines...")
        pipeline.train(baseline, contamination=args.contamination)
        print(f"  malformed lines: {pipeline.malformed_line_count}")

        report("held-out normal", pipeline.detect(normal_eval))
        report("heuristic-attack", pipeline.detect(attack_eval))


if __name__ == "__main__":
    main()
