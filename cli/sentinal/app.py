"""sentinal: the sentinel-agent CLI (spec §8, /cli README).

Core loop for `run`: launch the user's container -> run the local startup
vulnerability scan (secrets/CVE/docker-misconfig/weak-creds) -> block on
critical findings -> stream container logs into /model's LogPipeline ->
auto-train a baseline if this target has none yet -> ship anomaly + attack
events to core (best effort) and to the local dashboard API -> serve the
local ban API so core can coordinate an IP block when it flags an attacker.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import typer
import uvicorn

from sentinal import __version__
from sentinal._resources import is_frozen
from sentinal.ban_api import create_app as create_ban_app
from sentinal.build import BuildError, ensure_dockerfile
from sentinal.client import CoreClient
from sentinal.config import AgentConfig
from sentinal.container import ContainerError, ContainerRuntime
from sentinal.fim import FileIntegrityMonitor
from sentinal.local_api import create_app as create_status_app
from sentinal.pipeline import extract_source_ip, get_escalation_tracker, get_pipeline
from sentinal.scanner import run_startup_scan
from sentinal.state import AgentState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinal")

REPO_ROOT = Path(__file__).resolve().parents[2]  # cli/sentinal/app.py -> repo root (source checkout only)

# Where `sentinal upgrade` re-fetches the release binary from when installed as
# a packaged binary (not a source checkout). The installer detects arch, pulls
# the matching asset from the latest GitHub Release, and replaces the binary in
# place — same script as the one-line install.
INSTALL_URL = "https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh"


class _Shutdown(Exception):
    """Raised from the SIGTERM handler so `stop` triggers the same clean
    container-stop/config-cleanup path as Ctrl+C, instead of the process
    just dying mid-loop."""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _findings_path(target_id: str) -> Path:
    # Derived from AgentConfig.path_for (not the raw CONFIG_DIR constant) so
    # it honors the same directory AgentConfig itself resolves to, including
    # in tests that monkeypatch path_for.
    return AgentConfig.path_for(target_id).parent / f"{target_id}-startup-findings.json"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sentinal {__version__}")
        raise typer.Exit()


def _generate_session_id(seed: str) -> str:
    """Derives a short, readable target id from a path/image name (e.g.
    `sentinel-demo-app` -> `sentinel-demo-app-a1b2`) so `start` never
    requires the user to pick or remember one."""
    seed_path = Path(seed)
    if seed_path.exists():
        seed_path = seed_path.resolve()  # "." has an empty .name; resolve to the real folder name
    base = re.sub(r"[^a-z0-9]+", "-", seed_path.name.lower()).strip("-") or "app"
    while True:
        candidate = f"{base}-{secrets.token_hex(2)}"
        if not AgentConfig.path_for(candidate).exists():
            return candidate


def _resolve_admin_password(admin_password: str | None) -> str:
    if admin_password is None:
        admin_password = os.environ.get("SENTINAL_ADMIN_PASSWORD")
    if admin_password is None:
        admin_password = "admin"
        typer.echo("warning: no --admin-password/$SENTINAL_ADMIN_PASSWORD set — dashboard login defaults to 'admin'")
    return admin_password


def _docker_permission_hint(message: str) -> str | None:
    if "permission denied" in message.lower() and "docker.sock" in message.lower():
        return (
            "your user isn't in the 'docker' group, so it can't reach the Docker daemon. Fix once:\n"
            "    sudo usermod -aG docker $USER && newgrp docker\n"
            "(log out and back in if 'newgrp' doesn't pick it up right away). Running 'sudo sentinal' works "
            "too, but then sentinal's data (trained models, config) is written under root's home instead of "
            "yours — the docker group is the cleaner fix."
        )
    return None


app = typer.Typer(help="Sentinal sentinel-agent CLI")


@app.callback()
def main_callback(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit"),
) -> None:
    pass


@app.command()
def help(ctx: typer.Context) -> None:
    """Show all available commands (same as --help)."""
    # Take the context Typer/Click hands this command directly rather than
    # click.get_current_context() -- that one relies on a thread-local
    # context stack that isn't reliably populated the same way across
    # click versions (worked in dev, raised RuntimeError on a clean
    # Ubuntu/Python 3.10 install with a newer click).
    typer.echo(ctx.find_root().get_help())


@app.command()
def upgrade(
    skip_dashboard_build: bool = typer.Option(False, help="Skip rebuilding /dashboard's static assets (source-checkout dev installs only)"),
) -> None:
    """Updates sentinal to the latest release.

    Packaged binary (the normal install): re-runs the one-line installer, which
    pulls the latest release asset for this machine's arch and replaces the
    binary in place. Source checkout (dev): pulls the latest code and reinstalls
    the editable packages, equivalent to scripts/upgrade.sh.
    """
    if is_frozen():
        typer.echo("fetching the latest sentinal release ...")
        # Hand off to the same installer the one-liner uses — it detects arch,
        # downloads the matching asset, and installs over the current binary.
        # `bash -c 'curl ... | bash'` so we don't need curl-then-pipe plumbing
        # in Python; the installer handles sudo/PATH itself.
        result = subprocess.run(["bash", "-c", f'curl -fsSL "{INSTALL_URL}" | bash'])
        raise typer.Exit(code=result.returncode)

    if not (REPO_ROOT / ".git").exists():
        typer.echo(f"error: {REPO_ROOT} isn't a git checkout — can't self-upgrade. Pull manually and reinstall.")
        raise typer.Exit(code=1)

    typer.echo(f"pulling latest into {REPO_ROOT} ...")
    subprocess.run(["git", "pull"], cwd=REPO_ROOT, check=True)

    for pkg in ("model", "backend", "cli"):
        typer.echo(f"reinstalling {pkg} (editable) ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "-e", str(REPO_ROOT / pkg)], check=True)

    if not skip_dashboard_build and (REPO_ROOT / "dashboard").exists():
        typer.echo("rebuilding dashboard ...")
        result = subprocess.run(["npm", "run", "build"], cwd=REPO_ROOT / "dashboard")
        if result.returncode != 0:
            typer.echo("warning: dashboard build failed — npm installed? run `npm ci` in /dashboard and retry.")

    if os.name != "nt":
        venv_sentinal = Path(sys.executable).parent / "sentinal"
        bin_dir = Path("/usr/local/bin") if os.access("/usr/local/bin", os.W_OK) else Path.home() / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        symlink = bin_dir / "sentinal"
        symlink.unlink(missing_ok=True)
        symlink.symlink_to(venv_sentinal)

    version = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    typer.echo(f"upgraded to {version.stdout.strip()}")


@app.command()
def register(
    target_id: str = typer.Option(..., help="Unique id for this monitored target"),
    backend_url: str = typer.Option(..., help="Core backend base URL, e.g. http://localhost:8000"),
) -> None:
    """Registers this target with core and persists the deployment token.

    Degrades to a tokenless local config if core is unreachable — every
    other core-facing call in this CLI (send_events, trigger_scan) is
    already best-effort, so a target still works standalone (scan/run/
    dashboard) with no core backend running at all.
    """
    client = CoreClient(backend_url)
    try:
        token = client.register(target_id)
    except Exception:
        # Running standalone (no core backend) is a first-class, common mode —
        # don't dump a scary stack trace for it. Full detail stays at debug.
        logger.debug("core unreachable at %s — registering locally with no token", backend_url, exc_info=True)
        typer.echo(f"warning: couldn't reach core at {backend_url!r} — registered locally (no token; core-facing features stay best-effort)")
        token = None
    config = AgentConfig(target_id=target_id, backend_url=backend_url, token=token)
    path = config.save()
    typer.echo(f"registered target={target_id!r}, config saved to {path}")


@app.command()
def scan(
    target_id: str = typer.Option(..., help="Target id from a prior `register` call"),
    volume: list[str] = typer.Option([], "--volume", help="host[:container] path to scan; repeatable"),
) -> None:
    """Runs the local startup vulnerability scan standalone and prints findings.

    Runs locally (backend/vibesentinel_scanner) rather than round-tripping to
    core — core's Scanner endpoint doesn't exist yet, and the whole point of
    a pre-startup check is that it works with no backend running at all.
    """
    AgentConfig.load(target_id)  # validates target is registered
    result = run_startup_scan(volumes=volume, env=[], docker_inspect=None)
    if result is None:
        typer.echo("scan skipped: vibesentinel_scanner not installed")
        raise typer.Exit(code=1)
    typer.echo(f"scan complete: score={result.score} findings={len(result.findings)}")
    for f in result.findings:
        typer.echo(f"  [{f.severity}] {f.type}: {f.title}")


@app.command()
def run(
    target_id: str = typer.Option(
        None, help="Session/target id. Auto-generated from --path's folder name (or --image) if omitted — "
        "no prior `register` call needed."
    ),
    path: str = typer.Option(
        None, help="Path to your app's source (defaults to the current directory if neither --path nor "
        "--image is given). sentinal builds it (using your Dockerfile if you have one, otherwise "
        "auto-detecting Python/Node and generating one) and runs the result — you never run "
        "`docker build`/`docker run` yourself. Mutually exclusive with --image."
    ),
    image: str = typer.Option(
        None, help="An already-built image to run instead of building from --path, e.g. myapp:latest "
        "or a registry image you didn't build yourself."
    ),
    backend_url: str = typer.Option(
        "http://localhost:8000", help="Core backend URL, used only to auto-register if this target has no "
        "config yet — degrades to a local-only session if core isn't reachable."
    ),
    name: str = typer.Option(None, help="Container name"),
    port: list[str] = typer.Option([], "--port", help="Port mapping, e.g. 8080:8080; repeatable"),
    env: list[str] = typer.Option([], "--env", help="Env var KEY=VALUE; repeatable"),
    volume: list[str] = typer.Option([], "--volume", help="Bind mount host:container; repeatable"),
    ban_api_port: int = typer.Option(8787, help="Local port for the ban-action API"),
    status_api_port: int = typer.Option(8765, help="Local port for the dashboard status API"),
    force: bool = typer.Option(False, help="Start even if the startup scan finds critical issues"),
    batch_size: int = typer.Option(50, help="Log lines per detect() batch shipped to core"),
    baseline_lines: int = typer.Option(200, help="Log lines to auto-train a fresh target's anomaly baseline on, if not seeding from a pretrained model"),
    seed_model: str = typer.Option(
        "nginx", help="Pretrained dataset model to seed detection from (see model/README.md eval table) — "
        "'none' to cold-start on this target's own first log lines instead"
    ),
    retrain_every: int = typer.Option(
        500, help="Retrain the anomaly baseline on this many freshly observed normal-traffic lines "
        "(continuous improvement as the target runs) — 0 disables"
    ),
    foreground: bool = typer.Option(
        False, help="Stay attached and stream everything to this terminal instead of handing the watch "
        "loop off to a background process (Ctrl+C to stop). Useful under systemd/a process supervisor, "
        "or for debugging."
    ),
    admin_password: str = typer.Option(
        None, help="Password to log into the dashboard. Defaults to $SENTINAL_ADMIN_PASSWORD, or 'admin' "
        "with a printed warning if neither is set — change this for anything beyond local testing."
    ),
) -> None:
    """Builds (if --path) and launches the container, blocks on the startup
    scan, then hands the watch loop off to a background process and returns
    — control it afterward with `sentinal logs`/`scan`/`stop`/`status`. Run
    this from your app's own directory with no options for the one-command
    path: `sentinal run` (or the `sentinal start` alias) builds the current
    directory, picks a session id for you, and prints the dashboard link
    once it's up."""
    if path and image:
        typer.echo("error: pass at most one of --path (build from source) or --image (run an existing image)")
        raise typer.Exit(code=1)
    if not path and not image:
        path = "."

    if target_id is None:
        target_id = _generate_session_id(path or image)

    try:
        config = AgentConfig.load(target_id)
        typer.echo(f"session: {target_id}")
    except FileNotFoundError:
        client = CoreClient(backend_url)
        try:
            token = client.register(target_id)
        except Exception:
            # Standalone (no core backend) is the common case — keep it quiet;
            # the "registered locally" line below already says what happened.
            logger.debug("core unreachable at %s — registering locally with no token", backend_url, exc_info=True)
            token = None
        config = AgentConfig(target_id=target_id, backend_url=backend_url, token=token)
        config.save()
        typer.echo(f"session: {target_id} (new — registered{' locally, core unreachable' if token is None else ''})")

    client = CoreClient(config.backend_url, config.token)
    runtime = ContainerRuntime()

    # Fail fast with an actionable message if Docker isn't reachable, rather
    # than letting the build/run streams spew a raw daemon error.
    access_err = runtime.daemon_access_error()
    if access_err:
        hint = _docker_permission_hint(access_err)
        typer.echo("error: can't reach the Docker daemon.")
        typer.echo(hint if hint else access_err)
        raise typer.Exit(code=1)

    if path:
        tag = f"sentinal/{target_id}:latest"
        try:
            context_dir, dockerfile_path, generated = ensure_dockerfile(path)
        except BuildError as exc:
            typer.echo(f"error: {exc}")
            raise typer.Exit(code=1)
        typer.echo(
            f"{'generated a Dockerfile (no app-type Dockerfile found)' if generated else 'using existing Dockerfile'} "
            f"— building {tag} from {context_dir} ..."
        )
        try:
            runtime.build(str(context_dir), str(dockerfile_path), tag)
        except ContainerError as exc:
            typer.echo(f"error: {exc}")
            hint = _docker_permission_hint(str(exc))
            if hint:
                typer.echo(hint)
            raise typer.Exit(code=1)
        image = tag
        if not volume:
            volume = [f"{context_dir}:/app_source"]  # so the startup scanner can see your source too

    try:
        container_id = runtime.run(image=image, name=name, ports=port, env=env, volumes=volume)
    except ContainerError as exc:
        typer.echo(f"error: {exc}")
        hint = _docker_permission_hint(str(exc))
        if hint:
            typer.echo(hint)
        raise typer.Exit(code=1)
    typer.echo(f"container started: {container_id[:12]}")
    config.container_id = container_id
    config.save()

    typer.echo("running startup vulnerability scan...")
    try:
        inspect = runtime.inspect(container_id)
    except Exception:
        logger.warning("docker inspect failed — docker-config checks skipped", exc_info=True)
        inspect = None
    local_scan = run_startup_scan(volumes=volume, env=env, docker_inspect=inspect)

    findings = local_scan.findings if local_scan else []
    if local_scan is None:
        typer.echo("warning: startup scan skipped (vibesentinel_scanner not installed)")
    else:
        typer.echo(f"scan complete: score={local_scan.score} findings={len(findings)}")

    critical = [f for f in findings if f.severity == "critical"]
    if critical and not force:
        typer.echo(f"aborting: {len(critical)} critical finding(s) — rerun with --force to start anyway")
        for f in critical:
            typer.echo(f"  [critical] {f.type}: {f.title}")
        runtime.stop(container_id)
        raise typer.Exit(code=1)

    try:
        client.send_events(target_id, [
            {"type": "startup_finding", **dataclasses.asdict(f)} for f in findings
        ])
    except Exception:
        logger.debug("core unreachable for startup findings — continuing (dashboard still has them)", exc_info=True)

    admin_password = _resolve_admin_password(admin_password)

    loop_kwargs = dict(
        volume=volume, ban_api_port=ban_api_port, status_api_port=status_api_port,
        batch_size=batch_size, baseline_lines=baseline_lines, seed_model=seed_model,
        retrain_every=retrain_every, admin_password=admin_password,
    )

    if foreground:
        _monitor_body(target_id, config, client, runtime, container_id, findings, **loop_kwargs)
        return

    _findings_path(target_id).write_text(json.dumps([dataclasses.asdict(f) for f in findings]))
    # As a frozen binary, sys.executable IS the sentinal binary, so invoke the
    # `monitor` subcommand directly; `-m sentinal` only works from source where
    # sys.executable is the Python interpreter.
    if is_frozen():
        monitor_cmd = [sys.executable, "monitor", "--target-id", target_id]
    else:
        monitor_cmd = [sys.executable, "-m", "sentinal", "monitor", "--target-id", target_id]
    for key, value in loop_kwargs.items():
        if key == "volume":
            for v in value:
                monitor_cmd += ["--volume", v]
        else:
            monitor_cmd += [f"--{key.replace('_', '-')}", str(value)]

    log_path = AgentConfig.path_for(target_id).parent / f"{target_id}.log"
    log_file = open(log_path, "a")
    popen_kwargs = {} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(
        monitor_cmd, stdout=log_file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **popen_kwargs
    )
    config.pid = proc.pid
    config.save()

    typer.echo("")
    typer.echo(f"  dashboard ready -> http://localhost:{status_api_port}")
    typer.echo("")
    typer.echo(f"sentinal is watching {target_id!r} in the background (pid {proc.pid}):")
    typer.echo(f"  sentinal logs --target-id {target_id}     tail the container's output")
    typer.echo(f"  sentinal scan --target-id {target_id}     re-run the vulnerability scan")
    typer.echo(f"  sentinal status --target-id {target_id}   check what's running")
    typer.echo(f"  sentinal stop --target-id {target_id}     stop everything")
    typer.echo(f"(sentinal's own diagnostics, not the app's logs: {log_path})")


app.command("start", help="Alias for `run` — the one-command path: `sentinal start` from your app's directory.")(run)


@app.command(hidden=True)
def monitor(
    target_id: str = typer.Option(...),
    volume: list[str] = typer.Option([], "--volume"),
    ban_api_port: int = typer.Option(8787),
    status_api_port: int = typer.Option(8765),
    batch_size: int = typer.Option(50),
    baseline_lines: int = typer.Option(200),
    seed_model: str = typer.Option("nginx"),
    retrain_every: int = typer.Option(500),
    admin_password: str = typer.Option("admin"),
) -> None:
    """Internal: runs the background watch loop for a target `run`/`start`
    already launched a container for. Not meant to be invoked directly —
    `run`/`start` spawns this as a detached process and `stop` signals it."""
    config = AgentConfig.load(target_id)
    if not config.container_id:
        logger.error("monitor: target=%s has no container_id set — nothing to watch", target_id)
        raise typer.Exit(code=1)

    client = CoreClient(config.backend_url, config.token)
    runtime = ContainerRuntime()

    findings: list[dict] = []
    findings_path = _findings_path(target_id)
    if findings_path.exists():
        try:
            findings = json.loads(findings_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass

    _monitor_body(
        target_id, config, client, runtime, config.container_id, findings,
        volume=volume, ban_api_port=ban_api_port, status_api_port=status_api_port,
        batch_size=batch_size, baseline_lines=baseline_lines, seed_model=seed_model,
        retrain_every=retrain_every, admin_password=admin_password, findings_are_dicts=True,
    )


def _monitor_body(
    target_id: str,
    config: AgentConfig,
    client: CoreClient,
    runtime: ContainerRuntime,
    container_id: str,
    findings,
    *,
    volume: list[str],
    ban_api_port: int,
    status_api_port: int,
    batch_size: int,
    baseline_lines: int,
    seed_model: str,
    retrain_every: int,
    admin_password: str,
    findings_are_dicts: bool = False,
) -> None:
    """The actual watch loop: ban API + dashboard status API + FIM + log
    streaming into detection. Runs either inline (`run --foreground`) or,
    normally, inside the detached `monitor` process `run`/`start` spawns."""
    agent_state = AgentState(target_id=target_id)
    agent_state.set_findings(findings if findings_are_dicts else [dataclasses.asdict(f) for f in findings])

    signal.signal(signal.SIGTERM, lambda signum, frame: (_ for _ in ()).throw(_Shutdown()))

    ban_thread = threading.Thread(
        target=uvicorn.run,
        args=(create_ban_app(container_id, runtime),),
        kwargs={"host": "127.0.0.1", "port": ban_api_port, "log_level": "warning"},
        daemon=True,
    )
    ban_thread.start()
    logger.info("ban API listening on 127.0.0.1:%d", ban_api_port)

    status_thread = threading.Thread(
        target=uvicorn.run,
        args=(create_status_app(agent_state, runtime, admin_password=admin_password),),
        kwargs={"host": "127.0.0.1", "port": status_api_port, "log_level": "warning"},
        daemon=True,
    )
    status_thread.start()
    logger.info("dashboard ready -> http://localhost:%d", status_api_port)

    fim_paths = [v.split(":")[0] for v in volume]
    if fim_paths:
        fim = FileIntegrityMonitor(
            root=fim_paths[0],
            critical_globs=config.critical_globs,
            baseline_path=f".sentinal/{target_id}-fim-baseline.json",
        )

        def on_file_change(path, is_critical) -> None:
            client.send_events(target_id, [{"type": "fim_change", "path": str(path), "critical": is_critical}])
            agent_state.add_attack({
                "type": "fim_change",
                "message": f"file changed: {path}",
                "kind": "warning" if is_critical else "neutral",
                "actor": "FIM",
            })

        threading.Thread(target=fim.watch, args=(on_file_change,), daemon=True).start()

    pipeline = get_pipeline(target_id)
    tracker = get_escalation_tracker()
    if pipeline is None:
        logger.warning("anomaly detection disabled (no /model artifacts) — log tailing only")

    seeded = False
    if pipeline is not None and seed_model.lower() != "none":
        try:
            pipeline.seed_from_pretrained(seed_model)
            seeded = True
            logger.info("anomaly detection seeded from pretrained model=%r — active immediately", seed_model)
        except FileNotFoundError:
            available = pipeline.available_pretrained()
            logger.warning("no pretrained model %r (available: %s) — cold-starting instead", seed_model, available)

    pipeline_box = {
        "pipeline": pipeline,
        "trained": pipeline is None or seeded,
        "normal_buffer": [],
        "retrain_every": retrain_every,
    }
    buffer: list[str] = []
    try:
        for line in runtime.logs(container_id):
            buffer.append(line)

            if not pipeline_box["trained"]:
                if len(buffer) < baseline_lines:
                    continue
                _train_baseline(pipeline_box, target_id, buffer)
                buffer = []
                continue

            if len(buffer) < batch_size:
                continue
            _flush(pipeline_box, tracker, client, agent_state, target_id, buffer)
            buffer = []
    except (KeyboardInterrupt, _Shutdown):
        pass
    finally:
        if buffer and pipeline_box["trained"]:
            _flush(pipeline_box, tracker, client, agent_state, target_id, buffer)
        logger.info("stopping container %s", container_id[:12])
        runtime.stop(container_id)
        config.container_id = None
        config.pid = None
        config.save()
        _findings_path(target_id).unlink(missing_ok=True)


def _train_baseline(pipeline_box: dict, target_id: str, lines: list[str]) -> None:
    """First `baseline_lines` of a fresh target's log stream become its
    Isolation Forest baseline — see model/README.md: train() expects
    known-normal traffic, and a target's own startup traffic is the closest
    thing to that this agent has without a separate manual step."""
    pipeline = pipeline_box["pipeline"]
    try:
        pipeline.train(lines)
        pipeline_box["trained"] = True
        logger.info("auto-trained baseline for target=%s on %d lines", target_id, len(lines))
    except ValueError:
        logger.warning("target=%s: not enough usable lines to train a baseline yet — detection stays off", target_id)
        pipeline_box["pipeline"] = None
        pipeline_box["trained"] = True


_RETRAIN_WINDOW_CAP = 3000  # matches model/README.md's baseline size for the shipped dataset models


def _maybe_retrain(pipeline_box: dict, target_id: str) -> None:
    """Continuous improvement: refit the baseline on this target's own
    recently observed normal traffic, on top of a seed or cold-start. Each
    refit versions the previous model (AnomalyModel._persist) rather than
    losing it."""
    retrain_every = pipeline_box["retrain_every"]
    if retrain_every <= 0:
        return
    buffer = pipeline_box["normal_buffer"]
    if len(buffer) < retrain_every:
        return

    window = buffer[-_RETRAIN_WINDOW_CAP:]
    try:
        pipeline_box["pipeline"].train(window)
        logger.info("retrained target=%s on %d accumulated normal lines", target_id, len(window))
    except ValueError:
        logger.warning("target=%s: retrain skipped (not enough usable lines)", target_id)
    pipeline_box["normal_buffer"] = []


def _flush(pipeline_box: dict, tracker, client: CoreClient, agent_state: AgentState, target_id: str, lines: list[str]) -> None:
    pipeline = pipeline_box["pipeline"]
    if pipeline is None:
        return

    try:
        results = pipeline.detect(lines)
    except FileNotFoundError:
        logger.warning("no trained model for target=%s — disabling detection for this run", target_id)
        pipeline_box["pipeline"] = None
        return

    now = time.time()
    events = []
    for line, r in zip(lines, results):
        if r.flag != -1:
            pipeline_box["normal_buffer"].append(line)
            continue
        events.append({"type": "log_anomaly", "template": r.template, "flag": r.flag, "severity_score": r.severity_score})
        agent_state.add_attack({
            "type": "log_anomaly",
            "message": f"anomalous log line matched template: {r.template}",
            "kind": "warning",
            "actor": "LogPipeline",
            "confidence": r.severity_score,
            "attack_type_guess": r.matched_signature,
        })

        if tracker is None:
            continue
        source_ip = extract_source_ip(line)
        if source_ip is None:
            continue
        attack_event = tracker.observe(source_ip, r, timestamp=now)
        if attack_event is not None:
            events.append({
                "type": "attack_event",
                "source_ip": attack_event.source_ip,
                "confidence": attack_event.confidence,
                "event_count": attack_event.event_count,
                "suggested_action": attack_event.suggested_action,
                "sample_templates": attack_event.sample_templates,
            })
            agent_state.add_attack({
                "type": "attack_event",
                "source_ip": attack_event.source_ip,
                "confidence": attack_event.confidence,
                "attack_type_guess": attack_event.suggested_action,
                "message": f"sustained anomalous activity from {attack_event.source_ip} — {attack_event.event_count} events, suggested: {attack_event.suggested_action}",
                "kind": "warning",
                "actor": attack_event.source_ip,
            })

    if events:
        try:
            client.send_events(target_id, events)
        except Exception:
            logger.debug("core unreachable for events batch — dashboard still has them", exc_info=True)

    _maybe_retrain(pipeline_box, target_id)


@app.command("fim-baseline")
def fim_baseline(
    root: str = typer.Option(..., help="Root path to hash"),
    target_id: str = typer.Option(..., help="Target id, used to namespace the baseline file"),
) -> None:
    """Builds (or rebuilds) the FIM baseline hash set."""
    config = AgentConfig.load(target_id)
    fim = FileIntegrityMonitor(
        root=root,
        critical_globs=config.critical_globs,
        baseline_path=f".sentinal/{target_id}-fim-baseline.json",
    )
    baseline = fim.build_baseline()
    typer.echo(f"baseline built: {len(baseline)} files")


@app.command("serve-ban-api")
def serve_ban_api(
    target_id: str = typer.Option(None, help="Target id — resolves its running container automatically, no raw docker ID needed"),
    container_id: str = typer.Option(None, help="Container id/name to scope ban actions to, if not using --target-id"),
    host: str = typer.Option("127.0.0.1", help="Bind host — keep loopback-only in production"),
    port: int = typer.Option(8787),
) -> None:
    """Runs the local ban-action API standalone (e.g. against an already-running container)."""
    container_id = _resolve_container_id(target_id, container_id)
    uvicorn.run(create_ban_app(container_id), host=host, port=port)


@app.command()
def stop(target_id: str = typer.Option(..., help="Target id — stops its background monitor and container")) -> None:
    """Stops a target's background monitor (if `run`/`start` spawned one)
    and its container, without needing a raw docker ID or PID."""
    config = AgentConfig.load(target_id)
    stopped_something = False

    if config.pid and _pid_alive(config.pid):
        typer.echo(f"stopping background monitor (pid {config.pid}) ...")
        os.kill(config.pid, signal.SIGTERM)
        for _ in range(50):  # up to ~5s for its own cleanup (stops the container, clears config) to land
            time.sleep(0.1)
            if not _pid_alive(config.pid):
                break
        stopped_something = True
        config = AgentConfig.load(target_id)  # reload -- the monitor's own exit path may have updated it

    if config.container_id:
        ContainerRuntime().stop(config.container_id)
        typer.echo(f"stopped container {config.container_id[:12]}")
        config.container_id = None
        stopped_something = True

    config.pid = None
    config.save()

    if not stopped_something:
        typer.echo(f"target={target_id!r} has nothing running")
        raise typer.Exit(code=1)


@app.command()
def logs(
    target_id: str = typer.Option(..., help="Target id — tails its running container's logs"),
    follow: bool = typer.Option(True, help="Keep streaming (Ctrl+C to stop); false prints what's buffered and exits"),
) -> None:
    """Tails a target's container logs without needing its raw docker ID."""
    config = AgentConfig.load(target_id)
    if not config.container_id:
        typer.echo(f"target={target_id!r} has no running container tracked")
        raise typer.Exit(code=1)
    try:
        for line in ContainerRuntime().logs(config.container_id, follow=follow, tail="all"):
            typer.echo(line)
    except KeyboardInterrupt:
        pass


def _resolve_container_id(target_id: str | None, container_id: str | None) -> str:
    if container_id:
        return container_id
    if target_id:
        config = AgentConfig.load(target_id)
        if config.container_id:
            return config.container_id
        typer.echo(f"error: target={target_id!r} has no running container tracked")
        raise typer.Exit(code=1)
    typer.echo("error: pass --target-id or --container-id")
    raise typer.Exit(code=1)


@app.command()
def status(target_id: str = typer.Option(...)) -> None:
    """Prints the persisted config for a target (includes its tracked container id, if running)."""
    config = AgentConfig.load(target_id)
    typer.echo(config.model_dump_json(indent=2))
    if config.pid:
        state = "running" if _pid_alive(config.pid) else "not running (stale pid)"
        typer.echo(f"background monitor: {state} (pid {config.pid})")


@app.command()
def core(
    host: str = typer.Option("127.0.0.1", help="bind host — use 0.0.0.0 to expose on the network"),
    port: int = typer.Option(8000, help="port to serve the dashboard + API on"),
    admin_password: str = typer.Option(
        None, help="dashboard login password (default 'admin' or $SENTINAL_ADMIN_PASSWORD) — set one before exposing on 0.0.0.0"
    ),
    reload: bool = typer.Option(False, help="auto-reload on code changes (dev/source only)"),
) -> None:
    """Starts the hosted management platform: dashboard + API, per-project Linux
    environments with two browser terminals, and live model monitoring. Open
    http://<host>:<port> once it's up (dashboard login password: 'admin' by
    default, override with --admin-password)."""
    if admin_password:
        os.environ["SENTINAL_ADMIN_PASSWORD"] = admin_password  # read at import by vibesentinel_core.main
    try:
        import uvicorn
        from vibesentinel_core.main import app as core_app
    except Exception as exc:  # noqa: BLE001
        typer.echo(
            f"error: hosted platform unavailable ({exc}). "
            "From a source checkout install it with: pip install -e './backend[core]'"
        )
        raise typer.Exit(code=1)

    typer.echo(f"sentinal core -> http://{host}:{port}  (Ctrl+C to stop)")
    if reload:
        # reload needs an import string so the worker can re-import on change —
        # source checkouts only (a frozen binary can't re-exec its modules).
        uvicorn.run("vibesentinel_core.main:app", host=host, port=port, reload=True, log_level="info")
    else:
        uvicorn.run(core_app, host=host, port=port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
