from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from server.common import path as common_path


class DatabaseConfiguration(BaseModel):
    """Only settings required to connect to the internal application database."""

    model_config = ConfigDict(extra="forbid", strict=True)

    backend: Literal["sqlite"] = "sqlite"
    database_path: str = Field(default="database.db", min_length=1, max_length=2048)
    insert_batch_size: int = Field(default=1000, ge=1, le=100000)

    def resolved_path(self, resources_root: Path | None = None) -> Path:
        path = Path(self.database_path).expanduser()
        root = resources_root or common_path.RESOURCES_ROOT
        return (path if path.is_absolute() else root / path).resolve()


class DatabaseConfigurationError(RuntimeError):
    pass


def configuration_path(resources_root: Path | None = None) -> Path:
    return (resources_root or common_path.RESOURCES_ROOT) / "database_config.json"


def load_database_configuration(
    resources_root: Path | None = None,
) -> DatabaseConfiguration:
    path = configuration_path(resources_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DatabaseConfiguration.model_validate(payload)
    except FileNotFoundError as exc:
        raise DatabaseConfigurationError("Database configuration has not been initialized") from exc
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DatabaseConfigurationError(f"Invalid database configuration: {exc}") from exc


def save_database_configuration(
    configuration: DatabaseConfiguration,
    resources_root: Path | None = None,
) -> None:
    path = configuration_path(resources_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(configuration.model_dump(), indent=2, sort_keys=True) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise DatabaseConfigurationError(f"Could not save database configuration: {exc}") from exc

