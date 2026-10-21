from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConfigurationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    backend: Literal["sqlite"] = "sqlite"
    database_path: str = Field(min_length=1, max_length=2048)
    insert_batch_size: int = Field(ge=1, le=100000)


class DatabaseConfigurationResponse(BaseModel):
    backend: Literal["sqlite"] = "sqlite"
    database_path: str = "database.db"
    insert_batch_size: int = 1000
    resolved_path: str | None = None
    connected: bool
    error: str | None = None


class DatabaseTestResponse(BaseModel):
    ok: bool
    message: str
