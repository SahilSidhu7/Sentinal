"""`sentinal-core` entry point — starts the hosted platform (dashboard + API).

Installed as a console script by backend[core], so the whole platform is one
command:

    sentinal-core                 # http://localhost:8000
    sentinal-core --host 0.0.0.0 --port 8080

For unattended/auto-start, run this under a process manager (systemd, docker,
supervisord) — see README "Auto-start". We deliberately don't daemonize on
install: a security tool shouldn't start a listening server without the
operator asking.
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="sentinal-core", description="VibeSentinel hosted platform (dashboard + API)")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (use 0.0.0.0 to expose on the network)")
    parser.add_argument("--port", type=int, default=8000, help="port to serve the dashboard + API on")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev only)")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "vibesentinel_core.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
