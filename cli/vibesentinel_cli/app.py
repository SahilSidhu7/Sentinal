"""vibesentinel-cli: the sentinel-agent CLI (spec §8, /cli README).

Commands: register, monitor (log tail -> LogPipeline -> ship events),
fim-baseline / fim-watch, serve-ban-api, status.
"""
from __future__ import annotations

import logging
import threading

import typer
import uvicorn

from vibesentinel_cli.ban_api import create_app
from vibesentinel_cli.client import CoreClient
from vibesentinel_cli.config import AgentConfig
from vibesentinel_cli.fim import FileIntegrityMonitor
from vibesentinel_cli.log_tail import tail_file
from vibesentinel_cli.pipeline import get_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vibesentinel_cli")

app = typer.Typer(help="VibeSentinel sentinel-agent CLI")


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
def monitor(
    target_id: str = typer.Option(..., help="Target id from a prior `register` call"),
    log_file: list[str] = typer.Option(..., "--log-file", help="Log file(s) to tail; repeatable"),
    root: str = typer.Option(".", help="Root path for the File Integrity Monitor"),
    batch_size: int = typer.Option(50, help="Log lines per detect() batch shipped to core"),
) -> None:
    """Tails logs into the anomaly pipeline, runs FIM, ships findings to core."""
    config = AgentConfig.load(target_id)
    client = CoreClient(config.backend_url, config.token)
    pipeline = get_pipeline(target_id)
    if pipeline is None:
        typer.echo("warning: anomaly detection disabled (no /model artifacts) — tailing only")

    fim = FileIntegrityMonitor(
        root=root,
        critical_globs=config.critical_globs,
        baseline_path=f".vibesentinel/{target_id}-fim-baseline.json",
    )

    def on_file_change(path, is_critical) -> None:
        client.send_events(target_id, [{
            "type": "fim_change",
            "path": str(path),
            "critical": is_critical,
        }])

    fim_thread = threading.Thread(target=fim.watch, args=(on_file_change,), daemon=True)
    fim_thread.start()

    buffer: list[str] = []
    for log_path in log_file:
        for line in tail_file(log_path):
            buffer.append(line)
            if len(buffer) < batch_size:
                continue
            _flush(pipeline, client, target_id, buffer)
            buffer = []


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
    root: str = typer.Option(".", help="Root path to hash"),
    target_id: str = typer.Option(..., help="Target id, used to namespace the baseline file"),
) -> None:
    """Builds (or rebuilds) the FIM baseline hash set."""
    config = AgentConfig.load(target_id)
    fim = FileIntegrityMonitor(
        root=root,
        critical_globs=config.critical_globs,
        baseline_path=f".vibesentinel/{target_id}-fim-baseline.json",
    )
    baseline = fim.build_baseline()
    typer.echo(f"baseline built: {len(baseline)} files")


@app.command("serve-ban-api")
def serve_ban_api(
    host: str = typer.Option("127.0.0.1", help="Bind host — keep loopback-only in production"),
    port: int = typer.Option(8787),
) -> None:
    """Runs the local ban-action API core calls into (agent-local, namespace-scoped)."""
    uvicorn.run(create_app(), host=host, port=port)


@app.command()
def status(target_id: str = typer.Option(...)) -> None:
    """Prints the persisted config for a target."""
    config = AgentConfig.load(target_id)
    typer.echo(config.model_dump_json(indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
