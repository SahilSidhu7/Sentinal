"""Scanner: aggregates all startup checks into one findings list + score
(spec Module 1 + Module 5 Fusion/Scoring). Runs against a container that's
already been started (needs `docker inspect` output) plus its bind-mounted
volumes on disk.

Contract other teams depend on (spec §8) — don't change without flagging
in /docs:
    Scanner().run(root_paths, env_pairs, docker_inspect) -> ScanResult
    ScanResult: findings: list[Finding], score: int
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import dependency_cve, docker_checks, secrets_scan, weak_credentials
from .findings import SEVERITY_DEDUCTION, Finding

STARTING_SCORE = 100
MIN_SCORE = 0


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    score: int = STARTING_SCORE
    malformed_checks: list[str] = field(default_factory=list)


class Scanner:
    """Stateless — safe to call `run()` repeatedly (e.g. once at container
    startup, then again on a schedule or on-demand from the dashboard)."""

    def run(
        self,
        root_paths: list[str] | None = None,
        env_pairs: list[str] | None = None,
        docker_inspect: dict | None = None,
    ) -> ScanResult:
        now = datetime.now(timezone.utc).isoformat()
        raw_hits: list[dict] = []
        malformed: list[str] = []

        for path in root_paths or []:
            try:
                raw_hits.extend(secrets_scan.scan_directory(path))
            except Exception as exc:  # noqa: BLE001 - one check failing shouldn't kill the scan
                malformed.append(f"secrets_scan({path}): {exc}")
            try:
                raw_hits.extend(dependency_cve.check_dependencies(path))
            except Exception as exc:  # noqa: BLE001
                malformed.append(f"dependency_cve({path}): {exc}")

        if env_pairs:
            try:
                raw_hits.extend(weak_credentials.check_env(env_pairs))
            except Exception as exc:  # noqa: BLE001
                malformed.append(f"weak_credentials: {exc}")

        if docker_inspect:
            try:
                raw_hits.extend(docker_checks.check_inspect(docker_inspect))
            except Exception as exc:  # noqa: BLE001
                malformed.append(f"docker_checks: {exc}")

        findings = [
            Finding(
                type=hit["type"],
                severity=hit["severity"],
                title=hit["title"],
                description=hit["description"],
                detected_at=now,
            )
            for hit in raw_hits
        ]

        score = STARTING_SCORE
        for f in findings:
            score -= SEVERITY_DEDUCTION.get(f.severity, 0)
        score = max(MIN_SCORE, score)

        return ScanResult(findings=findings, score=score, malformed_checks=malformed)
