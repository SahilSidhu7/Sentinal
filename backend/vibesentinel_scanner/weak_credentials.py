"""Default/weak-credential detection over a container's declared env vars
(spec Module 1) — catches the "admin/admin" class of misconfig that no
CVE database or secret-regex will ever flag.
"""
from __future__ import annotations

_WEAK_VALUES = {
    "admin", "password", "123456", "12345678", "root", "changeme",
    "admin123", "letmein", "password123", "guest", "test", "default",
}

_CRED_KEY_HINTS = ("password", "passwd", "pwd", "secret", "token", "api_key", "apikey")


def check_env(env_pairs: list[str]) -> list[dict]:
    """`env_pairs` are raw `KEY=VALUE` strings (as passed to `docker run -e`
    or read back from `docker inspect`'s Config.Env)."""
    hits: list[dict] = []
    for pair in env_pairs:
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key_lower = key.lower()
        value_lower = value.strip().lower()

        if not any(hint in key_lower for hint in _CRED_KEY_HINTS):
            continue

        if value_lower in _WEAK_VALUES:
            hits.append({
                "type": "weak_credential",
                "severity": "critical",
                "title": f"Default/weak value for {key}",
                "description": f"Env var {key} is set to a common default ('{value}') — change it before exposing this service to any untrusted network.",
            })
        elif value_lower == key_lower or value_lower == key_lower.replace("_", ""):
            hits.append({
                "type": "weak_credential",
                "severity": "high",
                "title": f"{key} value matches its own key name",
                "description": f"Env var {key} appears set to a placeholder equal to its own name — looks like a template default that was never filled in.",
            })

    return hits
