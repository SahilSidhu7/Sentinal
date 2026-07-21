"""Regex-based weak labels for eval sanity-checking only.

These are NOT fed into AnomalyModel.train() — Isolation Forest training stays
unsupervised per spec §4. They exist purely to split held-out lines into
"probably normal" vs "probably attack" buckets so run_baseline_training.py
can report whether severity scores actually separate the two.
"""
import re

_PATTERNS = {
    "apache": re.compile(
        r"forbidden by rule|client denied|access denied|authentication required",
        re.IGNORECASE,
    ),
    "linux": re.compile(
        r"authentication failure|illegal user|invalid user|POSSIBLE BREAK-IN ATTEMPT|check pass; user unknown",
        re.IGNORECASE,
    ),
    "ssh": re.compile(
        r"Failed password|Invalid user|POSSIBLE BREAK-IN ATTEMPT|input_userauth_request: invalid user",
        re.IGNORECASE,
    ),
}


def is_suspicious(source: str, line: str) -> bool:
    pattern = _PATTERNS.get(source)
    return bool(pattern and pattern.search(line))
