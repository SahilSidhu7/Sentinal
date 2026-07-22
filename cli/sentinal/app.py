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
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import click
import typer
import uvicorn

from sentinal import __version__
from sentinal.ban_api import create_app as create_ban_app
from sentinal.client import CoreClient
from sentinal.config import AgentConfig
from sentinal.container import ContainerRuntime
from sentinal.fim import FileIntegrityMonitor
from sentinal.local_api import create_app as create_status_app
from sentinal.pipeline import extract_source_ip, get_escalation_tracker, get_pipeline
from sentinal.scanner import run_startup_scan
from sentinal.state import AgentState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinal")

REPO_ROOT = Path(__file__).resolve().parents[2]  # cli/sentinal/app.py -> repo root


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sentinal {__version__}")
        raise typer.Exit()


app = typer.Typer(help="Sentinal sentinel-agent CLI")


@app.callback()
def main_callback(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit"),
) -> None:
    pass


@app.command()
def help() -> None:
    """Show all available commands (same as --help)."""
    ctx = click.get_current_context()
    root = ctx.find_root()
    typer.echo(root.get_help())


@app.command()
def upgrade(
    skip_dashboard_build: bool = typer.Option(False, help="Skip rebuilding /dashboard's static assets"),
) -> None:
    """Pulls the latest code and reinstalls (editable) — run from a git checkout.

    Equivalent to scripts/upgrade.sh, exposed here so `sentinal upgrade` works
    once the CLI itself is on PATH, without needing the repo's script path.
    """
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
        logger.warning("core unreachable at %s — registering locally with no token", backend_url, exc_info=True)
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
    target_id: str = typer.Option(..., help="Target id from a prior `register` call"),
    image: str = typer.Option(..., help="Container image to launch, e.g. myapp:latest"),
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
) -> None:
    """Launches the container, blocks on the startup scan, then monitors it for its lifetime."""
    config = AgentConfig.load(target_id)
    client = CoreClient(config.backend_url, config.token)

    runtime = ContainerRuntime()
    container_id = runtime.run(image=image, name=name, ports=port, env=env, volumes=volume)
    typer.echo(f"container started: {container_id[:12]}")

    typer.echo("running startup vulnerability scan...")
    try:
        inspect = runtime.inspect(container_id)
    except Exception:
        logger.warning("docker inspect failed — docker-config checks skipped", exc_info=True)
        inspect = None
    local_scan = run_startup_scan(volumes=volume, env=env, docker_inspect=inspect)

    agent_state = AgentState(target_id=target_id)
    findings = local_scan.findings if local_scan else []
    agent_state.set_findings([dataclasses.asdict(f) for f in findings])
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

    ban_thread = threading.Thread(
        target=uvicorn.run,
        args=(create_ban_app(container_id, runtime),),
        kwargs={"host": "127.0.0.1", "port": ban_api_port, "log_level": "warning"},
        daemon=True,
    )
    ban_thread.start()
    typer.echo(f"ban API listening on 127.0.0.1:{ban_api_port} (backend coordinates IP blocks here)")

    status_thread = threading.Thread(
        target=uvicorn.run,
        args=(create_status_app(agent_state, runtime),),
        kwargs={"host": "127.0.0.1", "port": status_api_port, "log_level": "warning"},
        daemon=True,
    )
    status_thread.start()
    typer.echo(f"dashboard status API listening on 127.0.0.1:{status_api_port}")

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
        typer.echo("warning: anomaly detection disabled (no /model artifacts) — log tailing only")

    seeded = False
    if pipeline is not None and seed_model.lower() != "none":
        try:
            pipeline.seed_from_pretrained(seed_model)
            seeded = True
            typer.echo(f"anomaly detection seeded from pretrained model={seed_model!r} — active immediately")
        except FileNotFoundError:
            available = pipeline.available_pretrained()
            typer.echo(f"warning: no pretrained model {seed_model!r} (available: {available}) — cold-starting instead")

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
    except KeyboardInterrupt:
        pass
    finally:
        if buffer and pipeline_box["trained"]:
            _flush(pipeline_box, tracker, client, agent_state, target_id, buffer)
        typer.echo(f"stopping container {container_id[:12]}")
        runtime.stop(container_id)


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
    container_id: str = typer.Option(..., help="Container id/name to scope ban actions to"),
    host: str = typer.Option("127.0.0.1", help="Bind host — keep loopback-only in production"),
    port: int = typer.Option(8787),
) -> None:
    """Runs the local ban-action API standalone (e.g. against an already-running container)."""
    uvicorn.run(create_ban_app(container_id), host=host, port=port)


@app.command()
def status(target_id: str = typer.Option(...)) -> None:
    """Prints the persisted config for a target."""
    config = AgentConfig.load(target_id)
    typer.echo(config.model_dump_json(indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
