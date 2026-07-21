"""LogPipeline: the stable contract /cli and /backend import (spec §4, §8)."""
from __future__ import annotations

import logging

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

    def train(self, baseline_log_lines: list[str], *, contamination: float = 0.02) -> None:
        """Fits the target's Isolation Forest on a window of known-normal traffic.

        Trains on *distinct* templates, not raw lines: a handful of templates
        (e.g. one routine heartbeat message) can dominate raw line counts and
        would otherwise skew the forest's density estimate toward "whatever
        repeats most" rather than "what normal traffic actually looks like".
        """
        templates, malformed = self._templates_for(baseline_log_lines)
        self.malformed_line_count += malformed
        if not templates:
            raise ValueError("no usable templates extracted from baseline log lines")

        unique_templates = list(dict.fromkeys(templates))
        embeddings = self._embed_in_batches(unique_templates)
        self._anomaly_model.train(embeddings, contamination=contamination)
        logger.info(
            "trained target=%s raw_lines=%d unique_templates=%d malformed=%d",
            self.target_id, len(templates), len(unique_templates), malformed,
        )

    def detect(self, log_lines: list[str]) -> list[DetectionResult]:
        """Scores a batch of raw log lines. Malformed lines are skipped, not raised."""
        templates, malformed = self._templates_for(log_lines)
        self.malformed_line_count += malformed
        if not templates:
            return []

        embeddings = self._embed_in_batches(templates)
        return self._anomaly_model.detect(embeddings, templates)

    def _templates_for(self, log_lines: list[str]) -> tuple[list[str], int]:
        return self._parser.extract_batch(log_lines)

    def _embed_in_batches(self, templates: list[str]):
        import numpy as np

        chunks = [
            self._embedder.embed_batch(templates[i : i + self.batch_size])
            for i in range(0, len(templates), self.batch_size)
        ]
        return np.concatenate(chunks, axis=0)
