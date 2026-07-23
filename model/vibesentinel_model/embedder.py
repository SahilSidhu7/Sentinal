"""ONNX Runtime embedding of log templates via all-MiniLM-L6-v2 (spec §4 step 2).

Deliberately excludes PyTorch and the full `transformers` package — only
`onnxruntime` (inference) + `tokenizers` (fast Rust tokenizer) are required
at runtime, to keep install size and RAM low. Run scripts/export_onnx_model.py
once to produce the artifacts this class loads.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from ._resources import bundled_artifacts_dir

# The ONNX embedding model is a read-only shipped artifact — inside the frozen
# binary's bundle, or model/artifacts/ from a source checkout.
DEFAULT_ARTIFACTS_DIR = bundled_artifacts_dir() / "all-MiniLM-L6-v2"
MAX_SEQ_LEN = 64  # log templates are short; caps memory + latency per batch


class ModelArtifactsMissing(RuntimeError):
    pass


class TemplateEmbedder:
    """Batch-embeds log templates into fixed-size vectors (384-dim for MiniLM-L6)."""

    def __init__(self, artifacts_dir: str | Path = DEFAULT_ARTIFACTS_DIR):
        artifacts_dir = Path(artifacts_dir)
        model_path = artifacts_dir / "model.onnx"
        tokenizer_path = artifacts_dir / "tokenizer.json"

        if not model_path.exists() or not tokenizer_path.exists():
            raise ModelArtifactsMissing(
                f"missing {model_path} or {tokenizer_path} — run "
                "scripts/export_onnx_model.py first"
            )

        # single-threaded intra-op keeps this predictable/cheap on small hosts
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_padding(length=MAX_SEQ_LEN)
        self._tokenizer.enable_truncation(max_length=MAX_SEQ_LEN)

    def embed_batch(self, templates: list[str]) -> np.ndarray:
        """Returns an (N, 384) float32 array of mean-pooled sentence embeddings."""
        if not templates:
            return np.zeros((0, 384), dtype=np.float32)

        encodings = self._tokenizer.encode_batch(templates)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)

        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        token_embeddings = outputs[0]  # (N, seq_len, 384)
        return self._mean_pool(token_embeddings, attention_mask)

    @staticmethod
    def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        mask = attention_mask[..., None].astype(np.float32)
        summed = (token_embeddings * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = summed / counts
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled / np.clip(norms, a_min=1e-9, a_max=None)
