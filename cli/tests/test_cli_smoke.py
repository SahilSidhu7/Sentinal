import os
from pathlib import Path

from typer.testing import CliRunner

from sentinal.app import _docker_permission_hint, _generate_session_id, _pid_alive, app
from sentinal.config import AgentConfig
from sentinal.pipeline import get_pipeline

runner = CliRunner()


def _isolate_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sentinal.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr(AgentConfig, "path_for", classmethod(lambda cls, tid: tmp_path / f"{tid}.json"))


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

    # From-source (not frozen) path: a non-checkout dir can't self-upgrade.
    monkeypatch.setattr(app_module, "is_frozen", lambda: False)
    monkeypatch.setattr(app_module, "REPO_ROOT", tmp_path)
    result = runner.invoke(app, ["upgrade"])
    assert result.exit_code != 0
    assert "git checkout" in result.output


def test_upgrade_frozen_runs_installer(monkeypatch) -> None:
    # Packaged-binary path: upgrade re-runs the one-line installer instead of
    # touching git — and never shells out to the network in the test.
    import sentinal.app as app_module

    captured = {}

    class _Result:
        returncode = 0

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(app_module, "is_frozen", lambda: True)
    monkeypatch.setattr(app_module.subprocess, "run", _fake_run)

    result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 0
    assert any("install.sh" in str(part) for part in captured["cmd"])


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


def test_daemon_access_error_reports_permission_denied(monkeypatch) -> None:
    # The `docker info` preflight surfaces the permission-denied text so `run`
    # can turn it into the docker-group hint instead of a raw build failure.
    from sentinal.container import ContainerRuntime

    class _Result:
        returncode = 1
        stderr = "permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock"
        stdout = ""

    monkeypatch.setattr("sentinal.container.subprocess.run", lambda *a, **k: _Result())
    err = ContainerRuntime().daemon_access_error()
    assert err is not None
    assert _docker_permission_hint(err) is not None


def test_daemon_access_error_none_when_reachable(monkeypatch) -> None:
    from sentinal.container import ContainerRuntime

    class _Result:
        returncode = 0
        stderr = ""
        stdout = "Server Version: 27.0"

    monkeypatch.setattr("sentinal.container.subprocess.run", lambda *a, **k: _Result())
    assert ContainerRuntime().daemon_access_error() is None


def test_daemon_access_error_when_docker_missing(monkeypatch) -> None:
    from sentinal.container import ContainerRuntime

    def _raise(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr("sentinal.container.subprocess.run", _raise)
    err = ContainerRuntime().daemon_access_error()
    assert err is not None and "not found" in err


def test_monitor_command_is_hidden() -> None:
    # `monitor` is an internal implementation detail `run`/`start` spawn as a
    # background process -- callable directly (the child process invokes it),
    # but it shouldn't clutter the --help command list.
    from typer.main import get_command

    click_app = get_command(app)
    assert click_app.commands["monitor"].hidden is True


def test_pid_alive_true_for_current_process() -> None:
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_false_for_nonexistent_pid() -> None:
    # PIDs this large are never actually allocated -- a safe stand-in for "dead".
    assert _pid_alive(2**30) is False


def test_stop_reports_nothing_running(tmp_path, monkeypatch) -> None:
    _isolate_config(tmp_path, monkeypatch)
    AgentConfig(target_id="idle-target", backend_url="http://localhost:8000").save()

    result = runner.invoke(app, ["stop", "--target-id", "idle-target"])

    assert result.exit_code != 0
    assert "nothing running" in result.output


def test_stop_clears_stale_pid_with_no_container(tmp_path, monkeypatch) -> None:
    _isolate_config(tmp_path, monkeypatch)
    # A pid that's already dead (e.g. the background monitor crashed) must
    # not block `stop` from reporting cleanly -- nothing to kill, nothing to
    # wait on.
    AgentConfig(target_id="stale-target", backend_url="http://localhost:8000", pid=2**30).save()

    result = runner.invoke(app, ["stop", "--target-id", "stale-target"])

    assert result.exit_code != 0  # still "nothing running" -- the pid was already dead
    saved = AgentConfig.load("stale-target")
    assert saved.pid is None


def test_status_reports_background_monitor_state(tmp_path, monkeypatch) -> None:
    _isolate_config(tmp_path, monkeypatch)
    AgentConfig(target_id="watched-target", backend_url="http://localhost:8000", pid=os.getpid()).save()

    result = runner.invoke(app, ["status", "--target-id", "watched-target"])

    assert result.exit_code == 0
    assert "background monitor: running" in result.output


def test_monitor_requires_a_tracked_container(tmp_path, monkeypatch) -> None:
    _isolate_config(tmp_path, monkeypatch)
    AgentConfig(target_id="no-container-target", backend_url="http://localhost:8000").save()

    result = runner.invoke(app, ["monitor", "--target-id", "no-container-target"])

    assert result.exit_code != 0
