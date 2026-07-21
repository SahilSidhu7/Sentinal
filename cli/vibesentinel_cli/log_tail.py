"""Follows log files (nginx/apache/syslog/app logs), yielding new lines as they arrive."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator


def tail_file(path: str | Path, poll_interval: float = 0.5) -> Iterator[str]:
    """Yields new lines appended to `path`, starting from end-of-file, forever.

    Handles truncation/rotation by reopening when the file shrinks.
    """
    path = Path(path)
    while not path.exists():
        time.sleep(poll_interval)

    with path.open("r", errors="replace") as f:
        f.seek(0, 2)
        position = f.tell()
        while True:
            size = path.stat().st_size
            if size < position:
                f.seek(0)
                position = 0
            line = f.readline()
            if line:
                position = f.tell()
                yield line.rstrip("\n")
            else:
                time.sleep(poll_interval)
