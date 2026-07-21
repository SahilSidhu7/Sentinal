"""File Integrity Monitor: SHA256 baseline hashing + watchdog change flags (spec Module 2)."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


def _hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _is_critical(path: Path, critical_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(str(path), pattern) for pattern in critical_globs)


class FileIntegrityMonitor:
    def __init__(self, root: str | Path, critical_globs: list[str], baseline_path: str | Path):
        self.root = Path(root)
        self.critical_globs = critical_globs
        self.baseline_path = Path(baseline_path)

    def build_baseline(self) -> dict[str, str]:
        baseline = {
            str(p): h
            for p in self.root.rglob("*")
            if p.is_file() and (h := _hash_file(p)) is not None
        }
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(json.dumps(baseline, indent=2))
        logger.info("FIM baseline: %d files hashed under %s", len(baseline), self.root)
        return baseline

    def load_baseline(self) -> dict[str, str]:
        if not self.baseline_path.exists():
            return self.build_baseline()
        return json.loads(self.baseline_path.read_text())

    def watch(self, on_change) -> None:
        """Blocks, debounced, calling on_change(path, is_critical) for any content change."""
        baseline = self.load_baseline()
        monitor = self

        class Handler(FileSystemEventHandler):
            _last_seen: dict[str, float] = {}
            debounce_seconds = 0.5

            def on_modified(self, event):
                self._handle(event)

            def on_created(self, event):
                self._handle(event)

            def _handle(self, event):
                if event.is_directory:
                    return
                now = time.monotonic()
                last = self._last_seen.get(event.src_path, 0.0)
                if now - last < self.debounce_seconds:
                    return
                self._last_seen[event.src_path] = now

                path = Path(event.src_path)
                new_hash = _hash_file(path)
                if new_hash is not None and baseline.get(str(path)) != new_hash:
                    baseline[str(path)] = new_hash
                    on_change(path, _is_critical(path, monitor.critical_globs))

        observer = Observer()
        observer.schedule(Handler(), str(self.root), recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        finally:
            observer.stop()
            observer.join()
