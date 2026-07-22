"""Lazy access to `/model`'s LogPipeline — stubbed until ONNX artifacts exist.

Don't wait on `/model` finishing the ONNX export to wire the CLI: if the
pipeline or its artifacts aren't available yet, `get_pipeline` returns None
and callers should skip detection rather than crash the agent.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_pipeline(target_id: str):
    try:
        from vibesentinel_model.pipeline import LogPipeline
    except ImportError:
        logger.warning("vibesentinel_model not installed — detection disabled, tailing only")
        return None

    try:
        return LogPipeline(target_id=target_id)
    except Exception:
        logger.warning("LogPipeline init failed for target=%s — detection disabled", target_id, exc_info=True)
        return None


def get_escalation_tracker():
    """New EscalationTracker, or None if /model isn't installed.

    One tracker per running agent process — its sliding window state must
    survive across the whole log stream, not get rebuilt per batch.
    """
    try:
        from vibesentinel_model import EscalationTracker
    except ImportError:
        return None
    return EscalationTracker()


def extract_source_ip(raw_line: str) -> str | None:
    try:
        from vibesentinel_model import extract_source_ip as _extract
    except ImportError:
        return None
    return _extract(raw_line)
