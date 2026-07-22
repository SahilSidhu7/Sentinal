"""Container-config misconfiguration checks (spec Module 1) against the
output of `docker inspect <container_id>` — no live probing, just config.
"""
from __future__ import annotations

DANGEROUS_PORTS = {
    "22": "SSH", "23": "Telnet", "2375": "Docker daemon (unencrypted)",
    "2376": "Docker daemon (TLS)", "3389": "RDP", "6379": "Redis",
    "9200": "Elasticsearch", "27017": "MongoDB", "5432": "PostgreSQL",
    "3306": "MySQL", "5984": "CouchDB", "11211": "Memcached",
}


def check_inspect(inspect: dict) -> list[dict]:
    """`inspect` is one element of `docker inspect <id>`'s JSON array."""
    hits: list[dict] = []
    host_config = inspect.get("HostConfig", {}) or {}
    config = inspect.get("Config", {}) or {}
    mounts = inspect.get("Mounts", []) or []

    if host_config.get("Privileged"):
        hits.append({
            "type": "docker_misconfig",
            "severity": "critical",
            "title": "Container running in privileged mode",
            "description": "--privileged grants near-host-equivalent access; a container compromise becomes a host compromise. Drop specific capabilities with --cap-add instead.",
        })

    for m in mounts:
        source = str(m.get("Source", ""))
        if source.endswith("docker.sock"):
            hits.append({
                "type": "docker_misconfig",
                "severity": "critical",
                "title": "Docker socket mounted into container",
                "description": f"{source} is bind-mounted in — any process in this container can control the host's Docker daemon (container escape).",
            })

    user = str(config.get("User", "") or "")
    if user in ("", "0", "root"):
        hits.append({
            "type": "docker_misconfig",
            "severity": "medium",
            "title": "Container runs as root",
            "description": "No non-root USER set — a container-escape or arbitrary-write bug hands the attacker root inside the container. Set USER in the image or --user at run time.",
        })

    port_bindings = host_config.get("PortBindings", {}) or {}
    for container_port, bindings in port_bindings.items():
        port = container_port.split("/")[0]
        label = DANGEROUS_PORTS.get(port)
        if not label:
            continue
        for b in bindings or []:
            host_ip = b.get("HostIp", "")
            if host_ip in ("", "0.0.0.0", "::"):
                hits.append({
                    "type": "docker_misconfig",
                    "severity": "high",
                    "title": f"{label} port {port} exposed to all interfaces",
                    "description": f"Container port {port} ({label}) is bound to {host_ip or '0.0.0.0'} — reachable from any network the host is on, not just localhost. Bind to 127.0.0.1 or a firewalled interface if it doesn't need to be public.",
                })

    memory = host_config.get("Memory", 0) or 0
    if memory == 0:
        hits.append({
            "type": "docker_misconfig",
            "severity": "low",
            "title": "No memory limit set",
            "description": "Container has no --memory cap — a runaway process (or a resource-exhaustion attack) can take down the whole host.",
        })

    return hits
