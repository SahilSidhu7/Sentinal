"""sentinal: the sentinel-agent CLI (spec §8, /cli README).

Core loop for `run`: launch the user's container -> block on backend's
startup scan (secrets/CVE/leaks) -> stream container logs into /model's
LogPipeline -> ship anomaly events to core -> serve the local ban API so
core can coordinate an IP block when it flags an attacker.
"""
from __future__ import annotations

import logging
import threading

import typer
import uvicorn

from sentinal.ban_api import create_app
from sentinal.client import CoreClient
from sentinal.config import AgentConfig
from sentinal.container import ContainerRuntime
from sentinal.fim import FileIntegrityMonitor
from sentinal.pipeline import get_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinal")

app = typer.Typer(help="Sentinal sentinel-agent CLI")


@app.command()
def register(
    target_id: str = typer.Option(..., help="Unique id for this monitored target"),
    backend_url: str = typer.Option(..., help="Core backend base URL, e.g. http://localhost:8000"),
) -> None:
    """Registers this target with core and persists the deployment token."""
    client = CoreClient(backend_url)
    token = client.register(target_id)
    config = AgentConfig(target_id=target_id, backend_url=backend_url, token=token)
    path = config.save()
    typer.echo(f"registered target={target_id!r}, config saved to {path}")


@app.command()
def scan(
    target_id: str = typer.Option(..., help="Target id from a prior `register` call"),
) -> None:
    """Triggers the backend's startup Scanner (secrets/CVE/leaks) and prints findings."""
    config = AgentConfig.load(target_id)
    client = CoreClient(config.backend_url, config.token)
    result = client.trigger_scan(target_id)
    findings = result.get("findings", [])
    score = result.get("score")
    typer.echo(f"scan complete: score={score} findings={len(findings)}")
    for f in findings:
        typer.echo(f"  [{f.get('severity', '?')}] {f.get('type', '?')}: {f.get('summary', '')}")


@app.command()
def run(
    target_id: str = typer.Option(..., help="Target id from a prior `register` call"),
    image: str = typer.Option(..., help="Container image to launch, e.g. myapp:latest"),
    name: str = typer.Option(None, help="Container name"),
    port: list[str] = typer.Option([], "--port", help="Port mapping, e.g. 8080:8080; repeatable"),
    env: list[str] = typer.Option([], "--env", help="Env var KEY=VALUE; repeatable"),
    volume: list[str] = typer.Option([], "--volume", help="Bind mount host:container; repeatable"),
    ban_api_port: int = typer.Option(8787, help="Local port for the ban-action API"),
    force: bool = typer.Option(False, help="Start even if the startup scan finds critical issues"),
    batch_size: int = typer.Option(50, help="Log lines per detect() batch shipped to core"),
) -> None:
    """Launches the container, blocks on the startup scan, then monitors it for its lifetime."""
    config = AgentConfig.load(target_id)
    client = CoreClient(config.backend_url, config.token)

    typer.echo("running startup scan...")
    try:
        scan_result = client.trigger_scan(target_id)
    except Exception:
        logger.warning("startup scan unreachable — proceeding without it", exc_info=True)
        scan_result = {"findings": []}

    critical = [f for f in scan_result.get("findings", []) if f.get("severity") == "critical"]
    if critical and not force:
        typer.echo(f"aborting: {len(critical)} critical finding(s) — rerun with --force to start anyway")
        for f in critical:
            typer.echo(f"  [critical] {f.get('type', '?')}: {f.get('summary', '')}")
        raise typer.Exit(code=1)

    runtime = ContainerRuntime()
    container_id = runtime.run(image=image, name=name, ports=port, env=env, volumes=volume)
    typer.echo(f"container started: {container_id[:12]}")

    ban_thread = threading.Thread(
        target=uvicorn.run,
        args=(create_app(container_id, runtime),),
        kwargs={"host": "127.0.0.1", "port": ban_api_port, "log_level": "warning"},
        daemon=True,
    )
    ban_thread.start()
    typer.echo(f"ban API listening on 127.0.0.1:{ban_api_port} (backend coordinates IP blocks here)")

    fim_paths = [v.split(":")[0] for v in volume]
    if fim_paths:
        fim = FileIntegrityMonitor(
            root=fim_paths[0],
            critical_globs=config.critical_globs,
            baseline_path=f".sentinal/{target_id}-fim-baseline.json",
        )

        def on_file_change(path, is_critical) -> None:
            client.send_events(target_id, [{"type": "fim_change", "path": str(path), "critical": is_critical}])

        threading.Thread(target=fim.watch, args=(on_file_change,), daemon=True).start()

    pipeline = get_pipeline(target_id)
    if pipeline is None:
        typer.echo("warning: anomaly detection disabled (no /model artifacts) — log tailing only")

    buffer: list[str] = []
    try:
        for line in runtime.logs(container_id):
            buffer.append(line)
            if len(buffer) < batch_size:
                continue
            _flush(pipeline, client, target_id, buffer)
            buffer = []
    except KeyboardInterrupt:
        pass
    finally:
        if buffer:
            _flush(pipeline, client, target_id, buffer)
        typer.echo(f"stopping container {container_id[:12]}")
        runtime.stop(container_id)


def _flush(pipeline, client: CoreClient, target_id: str, lines: list[str]) -> None:
    if pipeline is None:
        return
    results = pipeline.detect(lines)
    events = [
        {"type": "log_anomaly", "template": r.template, "flag": r.flag, "severity_score": r.severity_score}
        for r in results
        if r.flag == -1
    ]
    if events:
        client.send_events(target_id, events)


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
    uvicorn.run(create_app(container_id), host=host, port=port)


@app.command()
def status(target_id: str = typer.Option(...)) -> None:
    """Prints the persisted config for a target."""
    config = AgentConfig.load(target_id)
    typer.echo(config.model_dump_json(indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
