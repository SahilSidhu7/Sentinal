from typer.testing import CliRunner

from vibesentinel_cli.app import app
from vibesentinel_cli.config import AgentConfig
from vibesentinel_cli.pipeline import get_pipeline

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "register" in result.output
    assert "monitor" in result.output


def test_status_missing_config_fails_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("vibesentinel_cli.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr(AgentConfig, "path_for", classmethod(lambda cls, tid: tmp_path / f"{tid}.json"))
    result = runner.invoke(app, ["status", "--target-id", "nonexistent"])
    assert result.exit_code != 0


def test_get_pipeline_without_model_package_returns_none() -> None:
    # /model may not be installed in this environment yet — must degrade, not raise.
    pipeline = get_pipeline("smoke-test-target")
    assert pipeline is None or hasattr(pipeline, "detect")
