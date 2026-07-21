"""LogPipeline: the stable contract /cli and /backend import (spec §4, §8)."""
from __future__ import annotations

import logging

from . import signatures
from .anomaly import AnomalyModel, DetectionResult
from .embedder import TemplateEmbedder
from .log_parser import LogTemplateExtractor

logger = logging.getLogger(__name__)

__all__ = ["LogPipeline", "DetectionResult"]

DEFAULT_BATCH_SIZE = 256


class LogPipeline:
    """Batch parse -> embed -> score pipeline for one monitored target.

    Don't rename train()/detect() or change DetectionResult's fields without
    updating /cli and /backend — they depend on this exact shape.
    """

    def __init__(self, target_id: str, batch_size: int = DEFAULT_BATCH_SIZE):
        self.target_id = target_id
        self.batch_size = batch_size
        self._parser = LogTemplateExtractor(target_id)
        self._embedder = TemplateEmbedder()
        self._anomaly_model = AnomalyModel(target_id)
        self.malformed_line_count = 0

    def train(self, baseline_log_lines: list[str], *, contamination: float = 0.05) -> None:
        """Fits the target's Isolation Forest on a window of known-normal traffic.

        Trains on raw-line template frequency, not deduped-to-unique templates:
        empirically this gave a much lower false-positive rate on real loghub
        data (see model/README.md eval history) — the forest's density estimate
        benefits from knowing how often a template actually recurs in normal
        traffic, not just that it occurred at all.
        """
        templates, _, malformed = self._templates_for(baseline_log_lines)
        self.malformed_line_count += malformed
        if not templates:
            raise ValueError("no usable templates extracted from baseline log lines")

        embeddings = self._embed_in_batches(templates)
        self._anomaly_model.train(embeddings, contamination=contamination)
        logger.info(
            "trained target=%s raw_lines=%d unique_templates=%d malformed=%d",
            self.target_id, len(templates), len(set(templates)), malformed,
        )

    def detect(self, log_lines: list[str]) -> list[DetectionResult]:
        """Scores a batch of raw log lines. Malformed lines are skipped, not raised.

        Combines the ML (structural/behavioral) result with a signature
        pre-filter (payload-content matches — SQLi/XSS/traversal/cmdi, see
        signatures.py): a signature hit always wins, forcing flag=-1 and a
        high severity, regardless of what the embedding-based score says.
        See model/README.md "Known limitation 2" for why the ML layer alone
        misses payload-content attacks and this combination is the fix.
        """
        templates, matched_lines, malformed = self._templates_for(log_lines)
        self.malformed_line_count += malformed
        if not templates:
            return []

        embeddings = self._embed_in_batches(templates)
        results = self._anomaly_model.detect(embeddings, templates)

        for i, line in enumerate(matched_lines):
            sig = signatures.match(line)
            if sig:
                results[i].flag = -1
                results[i].severity_score = max(results[i].severity_score, signatures.SIGNATURE_SEVERITY)
                results[i].matched_signature = sig.category
        return results

    def _templates_for(self, log_lines: list[str]) -> tuple[list[str], list[str], int]:
        return self._parser.extract_batch(log_lines)

    def _embed_in_batches(self, templates: list[str]):
        import numpy as np

        chunks = [
            self._embedder.embed_batch(templates[i : i + self.batch_size])
            for i in range(0, len(templates), self.batch_size)
        ]
        return np.concatenate(chunks, axis=0)
