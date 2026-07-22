"""Drain3-based log line -> template extraction (spec §4 step 1)."""
from __future__ import annotations

from pathlib import Path

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig


class MalformedLogLine(Exception):
    """Raised for lines Drain3 cannot reduce to a usable template."""


DEFAULT_STATE_DIR = Path(__file__).parent.parent / "artifacts" / "drain3_state"


class LogTemplateExtractor:
    """Wraps a per-target Drain3 TemplateMiner with disk persistence.

    One instance per monitored target — templates from different targets
    should never share a tree, or unrelated services start colliding.
    """

    def __init__(self, target_id: str, state_dir: str | Path = DEFAULT_STATE_DIR):
        self.target_id = target_id
        state_path = Path(state_dir) / f"{target_id}.bin"
        state_path.parent.mkdir(parents=True, exist_ok=True)

        config = TemplateMinerConfig()
        config.load(str(Path(__file__).parent / "drain3_config.ini"))
        config.profiling_enabled = False

        from drain3.file_persistence import FilePersistence

        self._miner = TemplateMiner(FilePersistence(str(state_path)), config=config)

    def extract(self, raw_line: str) -> str:
        """Return the log template for one line. Raises MalformedLogLine on failure."""
        line = raw_line.strip()
        if not line:
            raise MalformedLogLine("empty line")

        try:
            result = self._miner.add_log_message(line)
        except Exception as exc:  # Drain3 can throw on pathological input
            raise MalformedLogLine(str(exc)) from exc

        template = result.get("template_mined")
        if not template:
            raise MalformedLogLine("drain3 produced no template")
        return template

    def extract_batch(self, raw_lines: list[str]) -> tuple[list[str], list[str], int]:
        """Returns (templates, matched_lines, malformed_count).

        matched_lines[i] is the original raw line that produced templates[i] —
        preserved so callers can re-check the raw line (e.g. signature
        matching) against the same positions as the resulting embeddings.
        Never raises on a bad individual line.
        """
        templates: list[str] = []
        matched_lines: list[str] = []
        malformed = 0
        for line in raw_lines:
            try:
                templates.append(self.extract(line))
                matched_lines.append(line)
            except MalformedLogLine:
                malformed += 1
        return templates, matched_lines, malformed
