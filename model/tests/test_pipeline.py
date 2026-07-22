"""Tests exercise log_parser + anomaly against fixture data without requiring
real ONNX model artifacts — embeddings are stubbed with deterministic vectors
keyed by template hash, so CI doesn't need network access or the exported model.
"""
import numpy as np
import pytest

from vibesentinel_model.anomaly import AnomalyModel
from vibesentinel_model.log_parser import LogTemplateExtractor, MalformedLogLine


def test_template_extraction_normalizes_dynamic_values(tmp_path):
    extractor = LogTemplateExtractor("test-target", state_dir=tmp_path)
    t1 = extractor.extract('192.168.1.1 GET /api/users/42 200')
    t2 = extractor.extract('192.168.1.55 GET /api/users/7 200')
    assert t1 == t2  # same structure, different IP/id -> same template


def test_extract_batch_skips_malformed_lines(tmp_path):
    extractor = LogTemplateExtractor("test-target", state_dir=tmp_path)
    templates, matched_lines, malformed = extractor.extract_batch(["", "   ", "GET /health 200"])
    assert malformed == 2
    assert len(templates) == 1
    assert matched_lines == ["GET /health 200"]


def test_extract_raises_on_empty_line(tmp_path):
    extractor = LogTemplateExtractor("test-target", state_dir=tmp_path)
    with pytest.raises(MalformedLogLine):
        extractor.extract("")


def _fake_embeddings(n: int, anomalous: bool = False, dim: int = 384) -> np.ndarray:
    rng = np.random.default_rng(42 if not anomalous else 999)
    center = 0.0 if not anomalous else 5.0
    return rng.normal(loc=center, scale=1.0, size=(n, dim)).astype(np.float32)


def test_anomaly_model_train_and_detect(tmp_path):
    model = AnomalyModel("test-target", model_dir=tmp_path)
    baseline = _fake_embeddings(50, anomalous=False)
    model.train(baseline)

    normal_eval = _fake_embeddings(10, anomalous=False)
    attack_eval = _fake_embeddings(10, anomalous=True)

    normal_results = model.detect(normal_eval, templates=[f"t{i}" for i in range(10)])
    attack_results = model.detect(attack_eval, templates=[f"a{i}" for i in range(10)])

    avg_normal_severity = sum(r.severity_score for r in normal_results) / len(normal_results)
    avg_attack_severity = sum(r.severity_score for r in attack_results) / len(attack_results)
    assert avg_attack_severity > avg_normal_severity


def test_anomaly_model_persists_and_versions(tmp_path):
    model = AnomalyModel("test-target", model_dir=tmp_path)
    model.train(_fake_embeddings(20))
    model.train(_fake_embeddings(20))  # retrain -> should version the old file

    versioned = list(tmp_path.glob("test-target.log_anomaly_model.v*.joblib"))
    current = tmp_path / "test-target.log_anomaly_model.joblib"
    assert current.exists()
    assert len(versioned) == 1


def test_anomaly_model_train_requires_min_samples(tmp_path):
    model = AnomalyModel("test-target", model_dir=tmp_path)
    with pytest.raises(ValueError):
        model.train(_fake_embeddings(3))


def test_anomaly_model_seed_from_pretrained(tmp_path):
    source = AnomalyModel("nginx", model_dir=tmp_path)
    source.train(_fake_embeddings(30))

    target = AnomalyModel("fresh-target", model_dir=tmp_path)
    target.seed_from("nginx")

    assert (tmp_path / "fresh-target.log_anomaly_model.joblib").exists()
    # seeded model can detect immediately, no separate train() call needed
    results = target.detect(_fake_embeddings(5), templates=[f"t{i}" for i in range(5)])
    assert len(results) == 5


def test_anomaly_model_seed_from_missing_source_raises(tmp_path):
    target = AnomalyModel("fresh-target", model_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        target.seed_from("does-not-exist")


def test_anomaly_model_available_pretrained_lists_unversioned_only(tmp_path):
    AnomalyModel("nginx", model_dir=tmp_path).train(_fake_embeddings(20))
    AnomalyModel("nginx", model_dir=tmp_path).train(_fake_embeddings(20))  # creates a .v1 version
    AnomalyModel("apache", model_dir=tmp_path).train(_fake_embeddings(20))

    available = AnomalyModel("whatever", model_dir=tmp_path).available_pretrained()
    assert available == ["apache", "nginx"]
