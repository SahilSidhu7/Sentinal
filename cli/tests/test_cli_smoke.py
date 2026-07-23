from pathlib import Path

from typer.testing import CliRunner

from sentinal.app import _docker_permission_hint, _generate_session_id, app
from sentinal.config import AgentConfig
from sentinal.pipeline import get_pipeline

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "register" in result.output
    assert "run" in result.output
    assert "start" in result.output
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


def test_generate_session_id_uses_real_folder_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sentinal.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr(AgentConfig, "path_for", classmethod(lambda cls, tid: tmp_path / f"{tid}.json"))

    project_dir = tmp_path / "my-cool-app"
    project_dir.mkdir()

    # "." resolves to an empty Path.name -- must resolve to the actual
    # directory name rather than falling back to the generic "app".
    session_id = _generate_session_id(str(project_dir / "."))
    assert session_id.startswith("my-cool-app-")


def test_generate_session_id_avoids_collisions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sentinal.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr(AgentConfig, "path_for", classmethod(lambda cls, tid: tmp_path / f"{tid}.json"))

    first = _generate_session_id("demo")
    (tmp_path / f"{first}.json").write_text("{}")
    second = _generate_session_id("demo")
    assert first != second


def test_docker_permission_hint_matches_socket_error() -> None:
    hint = _docker_permission_hint("docker run failed: permission denied while trying to connect to the docker API at unix:///var/run/docker.sock")
    assert hint is not None
    assert "usermod -aG docker" in hint


def test_docker_permission_hint_ignores_unrelated_errors() -> None:
    assert _docker_permission_hint("docker run failed: no such image") is None
