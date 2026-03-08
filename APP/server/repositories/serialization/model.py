from __future__ import annotations

import json
import os
from typing import Any

from APP.server.common.constants import CHECKPOINT_PATH


###############################################################################
class ModelSerializer:
    """Template checkpoint metadata adapter."""

    def scan_checkpoints_folder(self) -> list[str]:
        if not os.path.isdir(CHECKPOINT_PATH):
            return []
        return sorted(
            [
                name
                for name in os.listdir(CHECKPOINT_PATH)
                if os.path.isdir(os.path.join(CHECKPOINT_PATH, name))
            ]
        )

    def load_training_configuration(
        self,
        checkpoint_path: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        config_path = os.path.join(checkpoint_path, "configuration.json")
        metadata_path = os.path.join(checkpoint_path, "metadata.json")
        session_path = os.path.join(checkpoint_path, "session.json")
        configuration = self._load_json(config_path, {"epochs": 0})
        metadata = self._load_json(metadata_path, {"template": True})
        session = self._load_json(session_path, {"epochs": 0, "history": {}})
        return configuration, metadata, session

    def _load_json(self, path: str, default: dict[str, Any]) -> dict[str, Any]:
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return default
        if isinstance(payload, dict):
            return payload
        return default
