from typer.testing import CliRunner

from sentinal.app import app
from sentinal.config import AgentConfig
from sentinal.pipeline import get_pipeline

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "register" in result.output
    assert "run" in result.output
    assert "scan" in result.output


def test_status_missing_config_fails_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sentinal.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr(AgentConfig, "path_for", classmethod(lambda cls, tid: tmp_path / f"{tid}.json"))
    result = runner.invoke(app, ["status", "--target-id", "nonexistent"])
    assert result.exit_code != 0


def test_get_pipeline_without_model_package_returns_none() -> None:
    # /model may not be installed in this environment yet — must degrade, not raise.
    pipeline = get_pipeline("smoke-test-target")
    assert pipeline is None or hasattr(pipeline, "detect")


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sentinal" in result.output


def test_help_command_matches_help_flag() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    assert "Commands" in result.output
    assert "register" in result.output


def test_upgrade_refuses_outside_git_checkout(tmp_path, monkeypatch) -> None:
    import sentinal.app as app_module

    monkeypatch.setattr(app_module, "REPO_ROOT", tmp_path)
    result = runner.invoke(app, ["upgrade"])
    assert result.exit_code != 0
    assert "git checkout" in result.output


def test_register_degrades_when_core_unreachable(tmp_path, monkeypatch) -> None:
    # Core backend doesn't exist yet — register must save a usable local
    # config instead of crashing, matching every other core-facing call in
    # this CLI (send_events, trigger_scan are already best-effort).
    monkeypatch.setattr("sentinal.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr(AgentConfig, "path_for", classmethod(lambda cls, tid: tmp_path / f"{tid}.json"))

    result = runner.invoke(app, ["register", "--target-id", "unreachable-test", "--backend-url", "http://localhost:1"])

    assert result.exit_code == 0
    assert "registered target=" in result.output
    saved = AgentConfig.load("unreachable-test")
    assert saved.token is None
