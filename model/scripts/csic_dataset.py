"""CSIC 2010 HTTP dataset -> HTTP-access-log-style lines with real ground-truth labels.

Rows in the CSV are one-per-request-*parameter* (grouped by the "index"
column) — reconstruct the full request line per group, or most "anom" rows
are just an innocuous parameter that happens to belong to an overall
anomalous request, diluting the real attack signal to near nothing.

Real labels ("norm"/"anom") replace the heuristic regex proxy labels used
for Apache/Linux/SSH — this is genuine attack traffic (SQLi, XSS, path
traversal, buffer overflow, parameter tampering), not an approximation.
See datasets/SOURCES.md for provenance/license notes (informal permission
from a mirror maintainer, not the original CSIC rights holder — kept
gitignored, never committed).
"""
from __future__ import annotations

import csv
import random
import zipfile
from itertools import groupby
from pathlib import Path
from urllib.parse import urlparse

DATASETS_DIR = Path(__file__).parent.parent / "datasets"
CSIC_ZIP = DATASETS_DIR / "csic2010_full.csv.zip"
CSIC_DIR = DATASETS_DIR / "_extracted" / "CSIC2010"
CSIC_CSV = CSIC_DIR / "full.csv"

_RNG = random.Random(20260722)
_NORMAL_IPS = [f"192.168.1.{i}" for i in range(2, 60)]
_ATTACK_IPS = [f"198.51.100.{i}" for i in range(2, 20)]


def ensure_extracted() -> Path:
    if CSIC_CSV.exists():
        return CSIC_CSV
    if not CSIC_ZIP.exists():
        raise FileNotFoundError(
            f"missing {CSIC_ZIP} — download from "
            "http://lexr.ai/csic_dataset/output_http_csic_2010_weka_with_duplications_RAW-RFC2616_escd_v02_full.csv.zip "
            "(see datasets/SOURCES.md)"
        )
    CSIC_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(CSIC_ZIP) as zf:
        (name,) = zf.namelist()
        with zf.open(name) as src, open(CSIC_CSV, "wb") as dst:
            dst.write(src.read())
    return CSIC_CSV


def _synthetic_ip(label: str) -> str:
    return _RNG.choice(_NORMAL_IPS if label == "norm" else _ATTACK_IPS)


def iter_csic_lines():
    """Yields (line, label) tuples, label in {'norm', 'anom'}, one per full request."""
    csv_path = ensure_extracted()
    with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
        rows = csv.DictReader(f)
        for _, group in groupby(rows, key=lambda r: (r["index"], r["method"], r["url"], r["label"])):
            group = list(group)
            first = group[0]
            params = [r["payload"] for r in group if r["payload"] not in ("null", "", None)]
            query = "&".join(params)

            path = urlparse(first["url"]).path or "/"
            label = first["label"]
            ip = _synthetic_ip(label)

            if first["method"] == "GET":
                request_line = f'{first["method"]} {path}{"?" + query if query else ""} {first["protocol"]}'
            else:
                request_line = f'{first["method"]} {path} {first["protocol"]}'

            body_suffix = f' BODY="{query}"' if query and first["method"] != "GET" else ""
            line = f'{ip} - - [08/Jul/2010:12:00:00 +0000] "{request_line}" 200{body_suffix}'
            yield line, label


if __name__ == "__main__":
    norm, anom = 0, 0
    for _, label in iter_csic_lines():
        norm += label == "norm"
        anom += label == "anom"
    print(f"norm={norm} anom={anom}")
