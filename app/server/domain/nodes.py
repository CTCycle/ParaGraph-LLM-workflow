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


class DatabaseSchemaRequest(BaseModel):
    node_type: Literal["SQL_DATABASE", "SQL_FILE_DATABASE"]
    node_version: int = Field(default=1, ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DatabaseSchemaColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Any | None = None
    primary_key: bool = False


class DatabaseSchemaPrimaryKey(BaseModel):
    name: str | None = None
    columns: list[str] = Field(default_factory=list)


class DatabaseSchemaForeignKey(BaseModel):
    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    referred_table: str | None = None
    referred_columns: list[str] = Field(default_factory=list)


class DatabaseSchemaIndex(BaseModel):
    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    unique: bool = False


class DatabaseSchemaTable(BaseModel):
    name: str
    columns: list[DatabaseSchemaColumn] = Field(default_factory=list)
    primary_key: DatabaseSchemaPrimaryKey
    foreign_keys: list[DatabaseSchemaForeignKey] = Field(default_factory=list)
    indexes: list[DatabaseSchemaIndex] = Field(default_factory=list)


class DatabaseSchemaResponse(BaseModel):
    tables: list[DatabaseSchemaTable] = Field(default_factory=list)


class VectorStoreConnectionCheckRequest(BaseModel):
    node_type: Literal["VECTOR_STORE"]
    node_version: int = Field(default=1, ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class VectorStoreConnectionCheckResponse(BaseModel):
    ok: bool
    message: str
