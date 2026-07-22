"""Docker lifecycle wrapper: sentinal launches and owns the monitored container.

Shells out to the `docker` CLI rather than the Docker SDK — no extra
dependency, and it's the same tool the operator already has installed
alongside `docker-compose` per the spec's tech stack.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Iterator

logger = logging.getLogger(__name__)


class ContainerError(RuntimeError):
    pass


class ContainerRuntime:
    def __init__(self, docker_bin: str = "docker"):
        self.docker_bin = docker_bin

    def run(
        self,
        image: str,
        name: str | None = None,
        ports: list[str] | None = None,
        env: list[str] | None = None,
        volumes: list[str] | None = None,
        command: list[str] | None = None,
    ) -> str:
        """Starts the container detached, with NET_ADMIN so the ban path can
        write firewall rules inside it later. Returns the container id."""
        args = [self.docker_bin, "run", "-d", "--cap-add", "NET_ADMIN"]
        if name:
            args += ["--name", name]
        for p in ports or []:
            args += ["-p", p]
        for e in env or []:
            args += ["-e", e]
        for v in volumes or []:
            args += ["-v", v]
        args.append(image)
        if command:
            args += command

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise ContainerError(f"docker run failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def logs(self, container_id: str, follow: bool = True) -> Iterator[str]:
        """Streams stdout/stderr lines from the container, tailing from now."""
        args = [self.docker_bin, "logs", "--tail", "0"]
        if follow:
            args.append("-f")
        args.append(container_id)

        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                yield line.rstrip("\n")
        finally:
            proc.terminate()

    def inspect(self, container_id: str) -> dict:
        """Returns the container's `docker inspect` config as a dict — the
        raw material for docker_checks.py's misconfiguration checks."""
        import json

        result = subprocess.run(
            [self.docker_bin, "inspect", container_id],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ContainerError(f"docker inspect failed: {result.stderr.strip()}")
        data = json.loads(result.stdout)
        return data[0] if data else {}

    def ps(self) -> list[dict]:
        """Lists containers this host's docker daemon knows about (for the
        dashboard's Containers view) — not scoped to ones sentinal launched."""
        import json

        result = subprocess.run(
            [self.docker_bin, "ps", "-a", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        containers = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return containers

    def exec(self, container_id: str, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.docker_bin, "exec", container_id, *cmd],
            capture_output=True,
            text=True,
        )

    def is_running(self, container_id: str) -> bool:
        result = subprocess.run(
            [self.docker_bin, "inspect", "-f", "{{.State.Running}}", container_id],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def stop(self, container_id: str) -> None:
        subprocess.run([self.docker_bin, "stop", container_id], capture_output=True, text=True)
