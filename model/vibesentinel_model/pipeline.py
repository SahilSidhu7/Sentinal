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

    def train(self, baseline_log_lines: list[str]) -> None:
        """Fits the target's Isolation Forest on a window of known-normal traffic."""
        templates, malformed = self._templates_for(baseline_log_lines)
        self.malformed_line_count += malformed
        if not templates:
            raise ValueError("no usable templates extracted from baseline log lines")

        embeddings = self._embed_in_batches(templates)
        self._anomaly_model.train(embeddings)
        logger.info(
            "trained target=%s samples=%d malformed=%d",
            self.target_id, len(templates), malformed,
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
