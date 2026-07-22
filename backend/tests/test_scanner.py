from pathlib import Path

from vibesentinel_scanner import Scanner
from vibesentinel_scanner.docker_checks import check_inspect
from vibesentinel_scanner.secrets_scan import scan_directory
from vibesentinel_scanner.weak_credentials import check_env


def test_secrets_scan_finds_aws_key(tmp_path: Path) -> None:
    (tmp_path / "config.py").write_text("AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n")
    hits = scan_directory(tmp_path)
    assert any(h["type"] == "secret" and h["severity"] == "critical" for h in hits)


def test_secrets_scan_flags_env_file_presence(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DB_PASSWORD=hunter2\n")
    hits = scan_directory(tmp_path)
    assert any("`.env` file present" in h["title"] or ".env file present" in h["title"] for h in hits)


def test_secrets_scan_skips_clean_file(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    assert scan_directory(tmp_path) == []


def test_docker_checks_flags_privileged() -> None:
    hits = check_inspect({"HostConfig": {"Privileged": True}, "Config": {"User": "app"}})
    assert any(h["title"].startswith("Container running in privileged") for h in hits)


def test_docker_checks_flags_docker_socket_mount() -> None:
    hits = check_inspect({
        "HostConfig": {},
        "Config": {"User": "app"},
        "Mounts": [{"Source": "/var/run/docker.sock"}],
    })
    assert any("Docker socket" in h["title"] for h in hits)


def test_docker_checks_flags_root_user() -> None:
    hits = check_inspect({"HostConfig": {}, "Config": {"User": ""}})
    assert any("runs as root" in h["title"] for h in hits)


def test_docker_checks_flags_exposed_dangerous_port() -> None:
    hits = check_inspect({
        "HostConfig": {"PortBindings": {"6379/tcp": [{"HostIp": "0.0.0.0", "HostPort": "6379"}]}},
        "Config": {"User": "app"},
    })
    assert any("Redis" in h["title"] for h in hits)


def test_weak_credentials_flags_default_password() -> None:
    hits = check_env(["DB_PASSWORD=admin", "UNRELATED=fine"])
    assert len(hits) == 1
    assert hits[0]["severity"] == "critical"


def test_weak_credentials_ignores_non_credential_keys() -> None:
    assert check_env(["PORT=8080", "NAME=myapp"]) == []


def test_scanner_run_aggregates_and_scores(tmp_path: Path) -> None:
    (tmp_path / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n-----END RSA PRIVATE KEY-----\n")
    result = Scanner().run(
        root_paths=[str(tmp_path)],
        env_pairs=["ADMIN_PASSWORD=admin123"],
        docker_inspect={"HostConfig": {"Privileged": True}, "Config": {"User": "app"}},
    )
    types = {f.type for f in result.findings}
    assert "secret" in types
    assert "weak_credential" in types
    assert "docker_misconfig" in types
    assert result.score < 100


def test_scanner_run_clean_target_scores_100(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n")
    result = Scanner().run(
        root_paths=[str(tmp_path)],
        env_pairs=["PORT=8080"],
        docker_inspect={"Config": {"User": "app"}, "HostConfig": {"Memory": 536870912}},
    )
    assert result.score == 100
    assert result.findings == []


def test_scanner_run_handles_missing_path_gracefully() -> None:
    result = Scanner().run(root_paths=["/does/not/exist"])
    assert result.findings == []
    assert result.score == 100
