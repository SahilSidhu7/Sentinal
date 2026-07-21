"""Per-target agent config: backend URL + deployment token, persisted locally."""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

CONFIG_DIR = Path(os.environ.get("VIBESENTINEL_HOME", Path.home() / ".vibesentinel"))


class AgentConfig(BaseModel):
    target_id: str
    backend_url: str
    token: str | None = None
    watch_paths: list[str] = []
    critical_globs: list[str] = ["*.env", "*.env.*", "**/config/**"]

    @staticmethod
    def path_for(target_id: str) -> Path:
        return CONFIG_DIR / f"{target_id}.json"

    def save(self) -> Path:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path = self.path_for(self.target_id)
        path.write_text(self.model_dump_json(indent=2))
        return path

    @classmethod
    def load(cls, target_id: str) -> "AgentConfig":
        path = cls.path_for(target_id)
        if not path.exists():
            raise FileNotFoundError(
                f"no config for target '{target_id}' at {path} — run `register` first"
            )
        return cls.model_validate(json.loads(path.read_text()))
