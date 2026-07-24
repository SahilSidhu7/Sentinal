"""Per-project Linux environment: one long-lived Docker container the user's
two terminals attach into.

Lifecycle (create/destroy/inspect) shells out to the `docker` CLI synchronously
— same approach as cli/sentinal/container.py, no SDK dependency. The terminal
bridge is async because it lives on the FastAPI event loop next to the
websocket it pumps bytes to.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess

from vibesentinel_core import _resources

logger = logging.getLogger("vibesentinel_core.environment")

ENV_IMAGE = "sentinal/env:latest"
CONTAINER_PREFIX = "sentinal-env-"


class EnvironmentError(RuntimeError):
    pass


class EnvironmentManager:
    def __init__(self, docker_bin: str = "docker"):
        self.docker_bin = docker_bin

    def container_name(self, project_id: str) -> str:
        return f"{CONTAINER_PREFIX}{project_id}"

    # -- image ------------------------------------------------------------

    def ensure_image(self) -> None:
        """Builds the environment image once if it isn't present. Called on
        first project creation so a fresh box just works."""
        probe = subprocess.run(
            [self.docker_bin, "image", "inspect", ENV_IMAGE],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            return
        logger.info("building environment image %s (first run) ...", ENV_IMAGE)
        build = subprocess.run(
            [self.docker_bin, "build", "-t", ENV_IMAGE, str(_resources.env_image_dir())],
        )
        if build.returncode != 0:
            raise EnvironmentError(
                f"failed to build {ENV_IMAGE} (exit {build.returncode}) — see output above"
            )

    # -- lifecycle --------------------------------------------------------

    def create(self, project_id: str) -> str:
        """Starts the environment container detached, kept alive by `sleep
        infinity`. Idempotent: an already-running env for this id is reused."""
        name = self.container_name(project_id)
        if self.is_running(project_id):
            return name
        # Remove a stopped leftover with the same name before recreating.
        subprocess.run([self.docker_bin, "rm", "-f", name], capture_output=True, text=True)
        result = subprocess.run(
            [self.docker_bin, "run", "-d", "--name", name, ENV_IMAGE],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise EnvironmentError(f"docker run failed: {result.stderr.strip()}")
        logger.info("created environment %s", name)
        return name

    def seed_demo(self, project_id: str) -> None:
        """Copies the demo server + traffic generator into one project's
        container (not baked into the base image — only a demo project gets
        them). Lands at /opt/demo_server.py and /opt/traffic.py."""
        name = self.container_name(project_id)
        for asset in ("demo_server.py", "traffic.py"):
            src = _resources.demo_assets_dir() / asset
            result = subprocess.run(
                [self.docker_bin, "cp", str(src), f"{name}:/opt/{asset}"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise EnvironmentError(f"docker cp {asset} failed: {result.stderr.strip()}")
        logger.info("seeded demo assets into %s", name)

    def destroy(self, project_id: str) -> None:
        subprocess.run(
            [self.docker_bin, "rm", "-f", self.container_name(project_id)],
            capture_output=True, text=True,
        )

    def is_running(self, project_id: str) -> bool:
        # Uses `docker ps` rather than `docker inspect`: the state query has to
        # agree with the operations we actually run (exec/logs), and `ps` is the
        # authoritative "is there a live container by this name" list.
        name = self.container_name(project_id)
        result = subprocess.run(
            [self.docker_bin, "ps", "--filter", f"name=^{name}$",
             "--filter", "status=running", "--format", "{{.Names}}"],
            capture_output=True, text=True,
        )
        return result.returncode == 0 and name in result.stdout.split()

    # -- terminal bridge --------------------------------------------------

    async def open_terminal(self, project_id: str) -> asyncio.subprocess.Process:
        """Attaches an interactive shell to the environment via the in-container
        PTY broker. Returns the process; caller pumps its stdin/stdout to a
        websocket. `-i` keeps stdin open, the broker owns the actual PTY."""
        name = self.container_name(project_id)
        return await asyncio.create_subprocess_exec(
            self.docker_bin, "exec", "-i", name,
            "python3", "/opt/ptybroker.py", "/bin/bash",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
