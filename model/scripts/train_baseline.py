"""Train + sanity-eval per-source Isolation Forest models on the datasets in
datasets/ (Apache, Linux, SSH — loghub; CSIC2010 — real web-attack traffic).
Real logs, not synthetic — see datasets/SOURCES.md for provenance.

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

from csic_dataset import iter_csic_lines
from heuristics import is_suspicious
from prepare_datasets import ensure_extracted, iter_lines

from vibesentinel_model.embedder import ModelArtifactsMissing
from vibesentinel_model.pipeline import LogPipeline

SEED = 20260721


def split_loghub(source: str, log_path: Path) -> tuple[list[str], list[str], str]:
    """Weak proxy labels via regex heuristic — see heuristics.py."""
    normal, suspicious = [], []
    for line in iter_lines(log_path):
        (suspicious if is_suspicious(source, line) else normal).append(line)
    return normal, suspicious, "heuristic-attack"


def split_csic() -> tuple[list[str], list[str], str]:
    """Real ground-truth labels from the dataset itself — norm/anom per request."""
    normal, attack = [], []
    for line, label in iter_csic_lines():
        (normal if label == "norm" else attack).append(line)
    return normal, attack, "real-attack"


def sample(lines: list[str], n: int, rng: random.Random) -> list[str]:
    if len(lines) <= n:
        return lines
    return rng.sample(lines, n)


def report(label: str, results) -> None:
    """Flag-based (raw IsolationForest -1/1, contamination-calibrated) is the
    primary metric — gives a much lower FP rate on real data than gating on
    severity_score alone. See EscalationTracker.observe, which gates the
    same way. avg_severity is secondary context, not the pass/fail signal.
    """
    if not results:
        print(f"    {label}: no lines")
        return
    flagged = sum(1 for r in results if r.flag == -1)
    avg_severity = sum(r.severity_score for r in results) / len(results)
    print(
        f"    {label}: n={len(results)} flagged={flagged} "
        f"({flagged / len(results):.0%}) avg_severity={avg_severity:.2f}"
    )


def train_and_eval(target_id: str, normal: list[str], attack: list[str], attack_label: str, args, rng) -> None:
    print(f"  total lines: normal={len(normal)} {attack_label}={len(attack)}")

    rng.shuffle(normal)
    baseline = normal[: args.baseline_size]
    normal_eval = normal[args.baseline_size : args.baseline_size + args.eval_size]
    attack_eval = sample(attack, args.eval_size, rng)

    if len(baseline) < 50:
        print(f"  [!] only {len(baseline)} normal lines, skipping (need >=50)")
        return

    try:
        pipeline = LogPipeline(target_id=target_id)
    except ModelArtifactsMissing as exc:
        print(f"[!] {exc}")
        sys.exit(1)

    print(f"  training on {len(baseline)} baseline lines...")
    pipeline.train(baseline, contamination=args.contamination)
    print(f"  malformed lines: {pipeline.malformed_line_count}")

    report("held-out normal", pipeline.detect(normal_eval))
    report(attack_label, pipeline.detect(attack_eval))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-size", type=int, default=3000)
    parser.add_argument("--eval-size", type=int, default=400)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument(
        "--with-csic",
        action="store_true",
        help="also train/eval on CSIC2010 (known not to separate with this approach — see README.md)",
    )
    args = parser.parse_args()

    rng = random.Random(SEED)
    paths = ensure_extracted()

    for source in ["apache", "linux", "ssh"]:
        print(f"\n=== {source} ===")
        normal, attack, attack_label = split_loghub(source, paths[source])
        train_and_eval(f"loghub-{source}", normal, attack, attack_label, args, rng)

    if args.with_csic:
        print("\n=== csic2010 (experimental, see README.md known limitation) ===")
        normal, attack, attack_label = split_csic()
        train_and_eval("csic2010", normal, attack, attack_label, args, rng)


if __name__ == "__main__":
    main()
