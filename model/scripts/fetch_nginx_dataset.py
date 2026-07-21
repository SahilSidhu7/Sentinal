"""Fetches recent daily nginx access logs from secrepo.com/self.logs/ (real
production traffic to Mike Sconzo's own site — CC-BY 4.0 licensed, no signup
required) and concatenates them into datasets/_extracted/Nginx/nginx.log.

Real traffic here includes genuine WordPress/exploit path-scanning bots
(wp-admin/*, xmlrpc.php, .env, phpmyadmin, ../ traversal attempts) mixed with
legitimate crawlers and visits — a real normal-vs-scanning-attack signal,
not synthetic.

Usage: python scripts/fetch_nginx_dataset.py [--days N]
"""
import argparse
import gzip
import sys
from pathlib import Path
from urllib.request import urlopen

BASE_URL = "https://www.secrepo.com/self.logs/"
DATASETS_DIR = Path(__file__).parent.parent / "datasets"
RAW_DIR = DATASETS_DIR / "_nginx_raw"
OUT_DIR = DATASETS_DIR / "_extracted" / "Nginx"
OUT_FILE = OUT_DIR / "nginx.log"


def list_available_files() -> list[str]:
    with urlopen(BASE_URL, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    import re

    names = sorted(set(re.findall(r'href="(access\.log\.[0-9-]+\.gz)"', html)))
    return names


def fetch_and_concat(days: int) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    filenames = list_available_files()[-days:]
    print(f"fetching {len(filenames)} daily log files...")

    with open(OUT_FILE, "wb") as out:
        for name in filenames:
            raw_path = RAW_DIR / name
            if not raw_path.exists():
                with urlopen(BASE_URL + name, timeout=20) as resp:
                    raw_path.write_bytes(resp.read())
            with gzip.open(raw_path, "rb") as f:
                out.write(f.read())

    print(f"wrote {OUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    fetch_and_concat(args.days)
