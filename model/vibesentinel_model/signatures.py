"""Known-payload signature pre-filter — catches what the ML layer structurally can't.

model/README.md "Known limitation 2" diagnosed why CSIC2010 (real SQLi/XSS/
traversal traffic) doesn't separate via Drain3+MiniLM+IsolationForest: a
mean-pooled sentence embedding of a full request line dilutes a short
injected payload inside otherwise-ordinary form text. That's a structural
limit of this ML approach, not something a contamination/threshold sweep
fixes — the correct tool for payload-content detection is a fast signature
match, same philosophy as Module 1's scanner (regex + entropy for secrets).

This module is deliberately NOT the primary detector for structural/
behavioral anomalies (brute force, scanning, volume drift) — Isolation
Forest already handles those well (see Apache/Linux/SSH numbers in
README.md). It exists specifically to catch payload content the embedding
approach misses, and its hits are combined with the ML result in
pipeline.detect(), not used standalone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote_plus

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("sqli", re.compile(
        r"(\bor\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+|\bunion\b.{0,40}\bselect\b|"
        r"\bdrop\s+table\b|\binsert\s+into\b.{0,40}\bvalues\b|--\s*$|;\s*--|"
        r"\bselect\b.{0,60}\bfrom\b.{0,60}\bwhere\b|\bsleep\(\d+\)|\bxp_cmdshell\b)",
        re.IGNORECASE,
    )),
    ("xss", re.compile(
        r"<script\b|javascript:|on(error|load|mouseover|click)\s*=|<img\b[^>]*onerror|"
        r"document\.(cookie|location)|<svg\b[^>]*onload|alert\s*\(",
        re.IGNORECASE,
    )),
    ("traversal", re.compile(
        r"\.\./\.\./|\.\.\\\.\.\\|%2e%2e[/\\]|/etc/passwd\b|\\windows\\win\.ini|"
        r"php://filter|\betc/shadow\b",
        re.IGNORECASE,
    )),
    ("cmdi", re.compile(
        r";\s*(cat|ls|whoami|wget|curl|nc|bash|sh)\b|\|\s*(cat|ls|whoami|id)\b|`.*`|\$\(.*\)",
    )),
    ("recon_probe", re.compile(
        r"wp-admin|wp-login|xmlrpc\.php|phpmyadmin|\.env\b|\.git/config|\.aws/credentials|"
        r"/actuator|/console\b|/\.well-known/security\.txt|cgi-bin/",
        re.IGNORECASE,
    )),
    ("overflow", re.compile(r"(.)\1{99,}")),  # 100+ repeated identical chars — classic fuzz/overflow probe
    ("crlf", re.compile(r"%0d%0a|\r\n\s*(set-cookie|location)\s*:", re.IGNORECASE)),
]

SIGNATURE_SEVERITY = 0.97  # forced severity on a signature hit — see pipeline.detect()


@dataclass
class SignatureMatch:
    category: str
    pattern: str


def match(line: str) -> SignatureMatch | None:
    """Returns the first matching known-payload signature, or None.

    Matches against both the raw line and its URL-decoded form — attack
    payloads in query strings/POST bodies are routinely percent-encoded
    (e.g. `%27%3B+DROP+TABLE` for `'; DROP TABLE`), which hides them from a
    literal regex unless decoded first.
    """
    try:
        decoded = unquote_plus(line)
        decoded_twice = unquote_plus(decoded)  # catches double-encoding evasion, e.g. %253C -> %3C -> <
    except Exception:
        decoded = decoded_twice = line

    for category, pattern in _PATTERNS:
        m = pattern.search(line) or pattern.search(decoded) or pattern.search(decoded_twice)
        if m:
            return SignatureMatch(category=category, pattern=m.group(0)[:60])
    return None
