from pathlib import Path

import pytest

from sentinal.build import BuildError, ensure_dockerfile


def test_uses_existing_dockerfile_unmodified(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")

    context_dir, resolved, generated = ensure_dockerfile(tmp_path)

    assert generated is False
    assert resolved == dockerfile
    assert resolved.read_text() == "FROM scratch\n"  # untouched


def test_generates_python_dockerfile_from_requirements_txt(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("flask\n")
    (tmp_path / "app.py").write_text("print('hi')\n")

    context_dir, resolved, generated = ensure_dockerfile(tmp_path)

    assert generated is True
    content = resolved.read_text()
    assert "python:3.11-slim" in content
    assert '"app.py"' in content
    assert not (tmp_path / "Dockerfile").exists()  # never written into the user's source tree


def test_generates_python_dockerfile_prefers_main_py_when_no_app_py(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("flask\n")
    (tmp_path / "main.py").write_text("print('hi')\n")

    _, resolved, _ = ensure_dockerfile(tmp_path)
    assert '"main.py"' in resolved.read_text()


def test_python_detection_fails_without_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("flask\n")
    with pytest.raises(BuildError):
        ensure_dockerfile(tmp_path)


def test_generates_node_dockerfile_from_package_json_start_script(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts": {"start": "node index.js"}}')

    _, resolved, generated = ensure_dockerfile(tmp_path)

    assert generated is True
    content = resolved.read_text()
    assert "node:20-slim" in content
    assert '["npm", "start"]' in content


def test_generates_node_dockerfile_from_entrypoint_file_without_start_script(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"dependencies": {"express": "^4.0.0"}}')
    (tmp_path / "server.js").write_text("// noop\n")

    _, resolved, _ = ensure_dockerfile(tmp_path)
    assert '["node", "server.js"]' in resolved.read_text()


def test_node_detection_fails_without_start_script_or_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    with pytest.raises(BuildError):
        ensure_dockerfile(tmp_path)


def test_no_manifest_at_all_raises(tmp_path: Path) -> None:
    (tmp_path / "readme.txt").write_text("nothing to see here\n")
    with pytest.raises(BuildError):
        ensure_dockerfile(tmp_path)


def test_not_a_directory_raises(tmp_path: Path) -> None:
    f = tmp_path / "notadir"
    f.write_text("x")
    with pytest.raises(BuildError):
        ensure_dockerfile(f)
