"""Extracts datasets/*.tar.gz once into datasets/_extracted/<name>/<name>.log."""
from __future__ import annotations

import tarfile
from pathlib import Path

DATASETS_DIR = Path(__file__).parent.parent / "datasets"
EXTRACTED_DIR = DATASETS_DIR / "_extracted"

SOURCES = ["Apache", "Linux", "SSH"]


def ensure_extracted() -> dict[str, Path]:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name in SOURCES:
        out_dir = EXTRACTED_DIR / name
        log_path = out_dir / f"{name}.log"
        if not log_path.exists():
            archive = DATASETS_DIR / f"{name}.tar.gz"
            if not archive.exists():
                raise FileNotFoundError(f"missing {archive}")
            out_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(out_dir)
        paths[name.lower()] = log_path
    return paths


def iter_lines(log_path: Path):
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                yield line


if __name__ == "__main__":
    for name, path in ensure_extracted().items():
        print(f"{name}: {path}")
