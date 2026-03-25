from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class UploadedDirectoryResponse(BaseModel):
    path: str
    file_count: int
    files: list[str] = Field(default_factory=list)


class DatabaseConnectionCheckRequest(BaseModel):
    node_type: Literal["SQL_DATABASE", "SQL_FILE_DATABASE"]
    node_version: int = Field(default=1, ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DatabaseConnectionCheckResponse(BaseModel):
    ok: bool
    message: str
