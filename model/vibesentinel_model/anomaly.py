"""Isolation Forest anomaly scoring over template embeddings (spec §4 step 3)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "artifacts" / "models"


@dataclass
class DetectionResult:
    template: str
    flag: int  # -1 = anomalous, 1 = normal (raw IsolationForest label)
    severity_score: float  # normalized 0.0-1.0, higher = more anomalous


class AnomalyModel:
    """Per-target Isolation Forest with joblib persistence + versioning."""

    def __init__(self, target_id: str, model_dir: str | Path = DEFAULT_MODEL_DIR):
        self.target_id = target_id
        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._forest: IsolationForest | None = None

    def _model_path(self, version: int | None = None) -> Path:
        suffix = f".v{version}" if version is not None else ""
        return self._model_dir / f"{self.target_id}.log_anomaly_model{suffix}.joblib"

    def train(self, embeddings: np.ndarray, *, contamination: float = 0.05) -> None:
        """Fits on the baseline distribution of a target's normal traffic."""
        if embeddings.shape[0] < 10:
            raise ValueError("need at least 10 baseline samples to fit a stable forest")

        forest = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=0,
            n_jobs=1,  # single-target hosts don't need parallel fit overhead
        )
        forest.fit(embeddings)
        self._forest = forest
        self._persist()

    def _persist(self) -> None:
        current = self._model_path()
        if current.exists():
            existing_versions = [
                int(p.suffixes[-2].lstrip(".v"))
                for p in self._model_dir.glob(f"{self.target_id}.log_anomaly_model.v*.joblib")
            ]
            next_version = max(existing_versions, default=0) + 1
            current.replace(self._model_path(version=next_version))
        joblib.dump(self._forest, current)

    def load(self) -> None:
        path = self._model_path()
        if not path.exists():
            raise FileNotFoundError(f"no trained model at {path} — call train() first")
        self._forest = joblib.load(path)

    def detect(self, embeddings: np.ndarray, templates: list[str]) -> list[DetectionResult]:
        if self._forest is None:
            self.load()
        if embeddings.shape[0] == 0:
            return []

        flags = self._forest.predict(embeddings)
        raw_scores = self._forest.decision_function(embeddings)
        severities = self._normalize(raw_scores)

        return [
            DetectionResult(template=t, flag=int(f), severity_score=float(s))
            for t, f, s in zip(templates, flags, severities)
        ]

    @staticmethod
    def _normalize(raw_scores: np.ndarray) -> np.ndarray:
        """decision_function: higher = more normal. Flip + squash to 0..1 anomaly severity."""
        inverted = -raw_scores
        lo, hi = inverted.min(), inverted.max()
        if hi - lo < 1e-9:
            return np.zeros_like(inverted)
        return (inverted - lo) / (hi - lo)
