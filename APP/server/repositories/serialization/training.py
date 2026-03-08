from __future__ import annotations

from typing import Any


###############################################################################
class TrainingSerializationAdapter:
    """Placeholder training serialization adapter for template wiring."""

    def save_training_snapshot(self, payload: dict[str, Any]) -> None:
        _ = payload

    def load_training_snapshot(self) -> dict[str, Any]:
        return {"template": True, "status": "empty"}
