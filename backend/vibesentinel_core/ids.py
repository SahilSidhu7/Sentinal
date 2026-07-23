"""Short, human-typable project ids.

A project gets one of these when the user doesn't name it. Users reach their
environment with the id, so it has to be short and unambiguous — Crockford
base32 (no I/L/O/U) over 6 chars gives ~1e9 space, plenty for a local box and
readable out loud.
"""
from __future__ import annotations

import re
import secrets

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32, ambiguous letters dropped
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def new_id(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def slugify(name: str) -> str:
    """Turns a user-supplied name into a container-safe id, or falls back to a
    generated one if nothing usable survives."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or new_id()
