from __future__ import annotations

import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pydantic import BaseModel, Field, field_validator, model_validator
from pypdf import PdfReader
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import (
    coerce_bool,
    coerce_float,
    coerce_int,
    coerce_text,
    parse_json_value,
)


SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".pdf", ".docx"}
SUPPORTED_DATABASE_ENGINES = {"sqlite", "postgresql"}
READ_ONLY_QUERY_PREFIXES = ("select", "with", "pragma", "show", "describe", "explain")


def _parse_string_list(value: Any, label: str) -> list[str]:
    parsed = parse_json_value(value, label) if isinstance(value, str) else value
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{label} must be a JSON array of strings")
    return [item.strip() for item in parsed if item.strip()]


def _parse_string_map(value: Any, label: str) -> dict[str, str]:
    parsed = parse_json_value(value, label) if isinstance(value, str) else value
    if not isinstance(parsed, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()):
        raise ValueError(f"{label} must be a JSON object with string values")
    return {key: item for key, item in parsed.items() if key.strip()}


class DocumentLoaderParameters(BaseModel):
    file_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_file_path(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if not payload.get("file_paths") and payload.get("file_path"):
            payload["file_paths"] = [payload["file_path"]]
        return payload

    @field_validator("file_paths", mode="before")
    @classmethod
    def validate_file_paths(cls, value: Any) -> list[str]:
        return _parse_string_list(value, "file_paths")

    @field_validator("file_paths")
    @classmethod
    def ensure_files_present(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("file_paths must contain at least one file path")
        return value


class DirectoryLoaderParameters(BaseModel):
    directory_path: str
    recursive: bool = True
    include_extensions: list[str] = Field(default_factory=lambda: sorted(SUPPORTED_DOCUMENT_EXTENSIONS))

    @field_validator("directory_path")
    @classmethod
    def validate_directory_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("directory_path must not be empty")
        return normalized

    @field_validator("include_extensions", mode="before")
    @classmethod
    def validate_extensions(cls, value: Any) -> list[str]:
        parsed = parse_json_value(value, "include_extensions") if isinstance(value, str) else value
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("include_extensions must be a JSON array of file extensions")
        return [item.lower() if item.startswith(".") else f".{item.lower()}" for item in parsed]


class WebScraperParameters(BaseModel):
    url: str
    timeout_s: float = Field(default=15.0, ge=1.0, le=120.0)
    strip_html_content: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("url must not be empty")
        return normalized


class ApiFetcherParameters(BaseModel):
    url: str
    request_urls: list[str] = Field(default_factory=list)
    timeout_s: float = Field(default=15.0, ge=1.0, le=120.0)
    response_selector: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    max_calls: int = Field(default=1, ge=1, le=100)
    allow_concurrency: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("url must not be empty")
        return normalized

    @field_validator("request_urls", mode="before")
    @classmethod
    def validate_request_urls(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return []
        return _parse_string_list(value, "request_urls")

    @field_validator("headers", mode="before")
    @classmethod
    def validate_headers(cls, value: Any) -> dict[str, str]:
        if value in (None, "", {}):
            return {}
        return _parse_string_map(value, "headers")


class DatabaseConnectionParameters(BaseModel):
    engine: str = "sqlite"
    database_name: str = ""
    host: str = ""
    port: int | None = 5432
    username: str = ""
    password: str = ""
    file_path: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    connect_timeout_s: float = Field(default=5.0, ge=1.0, le=60.0)

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_DATABASE_ENGINES:
            raise ValueError(f"engine must be one of: {', '.join(sorted(SUPPORTED_DATABASE_ENGINES))}")
        return normalized

    @field_validator("options", mode="before")
    @classmethod
    def validate_options(cls, value: Any) -> dict[str, Any]:
        if value in (None, "", {}):
            return {}
        parsed = parse_json_value(value, "options") if isinstance(value, str) else value
        if not isinstance(parsed, dict):
            raise ValueError("options must be a JSON object")
        return parsed

    @model_validator(mode="after")
    def validate_engine_specific_fields(self) -> DatabaseConnectionParameters:
        if self.engine == "sqlite":
            if not self.file_path.strip():
                raise ValueError("sqlite connections require file_path")
            return self

        if not self.host.strip():
            raise ValueError("postgresql connections require host")
        if not self.database_name.strip():
            raise ValueError("postgresql connections require database_name")
        if not self.username.strip():
            raise ValueError("postgresql connections require username")
        if self.port is None:
            raise ValueError("postgresql connections require port")
        return self


class DatabaseQueryParameters(BaseModel):
    query_text: str
    row_limit: int = Field(default=250, ge=1, le=5000)

    @field_validator("query_text")
    @classmethod
    def validate_query_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query_text must not be empty")
        return normalized


def _resolve_local_path(path_value: str) -> Path:
    return Path(path_value).expanduser().resolve()


def _make_document_id(source_uri: str) -> str:
    return str(uuid5(NAMESPACE_URL, source_uri))


def _html_to_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return "\n".join(part.strip() for part in soup.get_text("\n").splitlines() if part.strip())


def _load_docx_text(path: Path) -> str:
    document = Document(str(path))
    return "\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())


def _load_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        extracted = (page.extract_text() or "").strip()
        if extracted:
            parts.append(extracted)
    return "\n\n".join(parts)


def _load_file_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8"), mimetypes.guess_type(str(path))[0] or "text/plain"
    if suffix in {".html", ".htm"}:
        raw = path.read_text(encoding="utf-8")
        return _html_to_text(raw), mimetypes.guess_type(str(path))[0] or "text/html"
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        text_payload = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=True, default=str)
        return text_payload, "application/json"
    if suffix == ".pdf":
        return _load_pdf_text(path), "application/pdf"
    if suffix == ".docx":
        return _load_docx_text(path), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise ValueError(f"Unsupported document type: {path.suffix or path.name}")


def _build_document(source_uri: str, text_content: str, mime_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _make_document_id(source_uri),
        "text": text_content.strip(),
        "source_uri": source_uri,
        "mime_type": mime_type,
        "metadata": metadata,
    }


def _select_json_value(payload: Any, selector: str) -> Any:
    current = payload
    for part in selector.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current


def _coerce_api_targets(parameters: ApiFetcherParameters) -> list[str]:
    if parameters.request_urls:
        return parameters.request_urls[: parameters.max_calls]
    return [parameters.url]


def _coerce_response_text(response: httpx.Response, selector: str) -> tuple[str, str]:
    content_type = response.headers.get("content-type", "application/json").split(";")[0]
    if content_type == "application/json":
        payload = response.json()
        selected = _select_json_value(payload, selector) if selector else payload
        return (selected if isinstance(selected, str) else json.dumps(selected, indent=2, ensure_ascii=True, default=str), content_type)
    return response.text, content_type


async def _fetch_api_document_async(
    client: httpx.AsyncClient,
    target_url: str,
    timeout_s: float,
    selector: str,
    headers: dict[str, str],
    call_index: int,
) -> dict[str, Any]:
    response = await client.get(target_url, timeout=timeout_s, follow_redirects=True, headers=headers)
    response.raise_for_status()
    text_content, content_type = _coerce_response_text(response, selector)
    parsed = urlparse(str(response.url))
    return _build_document(
        str(response.url),
        text_content,
        content_type,
        {
            "host": parsed.netloc,
            "status_code": response.status_code,
            "call_index": call_index,
            "requested_url": target_url,
        },
    )


def _sync_fetch_api_documents(parameters: ApiFetcherParameters, targets: list[str]) -> list[dict[str, Any]]:
    headers = {"Accept": "application/json, text/plain;q=0.9, */*;q=0.8", **parameters.headers}
    documents: list[dict[str, Any]] = []
    for index, target_url in enumerate(targets):
        response = httpx.get(target_url, timeout=parameters.timeout_s, follow_redirects=True, headers=headers)
        response.raise_for_status()
        text_content, content_type = _coerce_response_text(response, parameters.response_selector)
        parsed = urlparse(str(response.url))
        documents.append(
            _build_document(
                str(response.url),
                text_content,
                content_type,
                {
                    "host": parsed.netloc,
                    "status_code": response.status_code,
                    "call_index": index,
                    "requested_url": target_url,
                },
            )
        )
    return documents


async def _concurrent_fetch_api_documents(parameters: ApiFetcherParameters, targets: list[str]) -> list[dict[str, Any]]:
    headers = {"Accept": "application/json, text/plain;q=0.9, */*;q=0.8", **parameters.headers}
    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_api_document_async(client, target_url, parameters.timeout_s, parameters.response_selector, headers, index)
            for index, target_url in enumerate(targets)
        ]
        return await asyncio.gather(*tasks)


def _build_database_url(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    engine = str(payload.get("engine") or "").strip().lower()
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    if engine == "sqlite":
        file_path = str(payload.get("file_path") or "").strip()
        if not file_path:
            raise ValueError("sqlite connections require file_path")
        resolved_file = _resolve_local_path(file_path)
        if not resolved_file.exists() or not resolved_file.is_file():
            raise ValueError(f"SQLite database file not found: {resolved_file}")
        return f"sqlite:///{resolved_file.as_posix()}", {}

    database_name = str(payload.get("database_name") or "").strip()
    host = str(payload.get("host") or "").strip()
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    port = payload.get("port")
    if not database_name or not host or not username or port is None:
        raise ValueError("postgresql connections require host, database_name, username, and port")

    query = {str(key): str(value) for key, value in options.items()}
    return (
        URL.create(
            "postgresql+psycopg",
            username=username,
            password=password or None,
            host=host,
            port=int(port),
            database=database_name,
            query=query,
        ).render_as_string(hide_password=False),
        {"connect_timeout": coerce_int(payload.get("connect_timeout_s"), 5)},
    )


def _sanitize_query_text(query_text: str) -> str:
    normalized = query_text.strip().rstrip(";").strip()
    if not normalized:
        raise ValueError("query_text must not be empty")
    if ";" in normalized:
        raise ValueError("database queries must contain exactly one read-only statement")
    prefix = normalized.split(None, 1)[0].lower() if normalized.split(None, 1) else ""
    if prefix not in READ_ONLY_QUERY_PREFIXES:
        raise ValueError("database queries are restricted to read-only statements")
    return normalized


def _document_loader_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    raw_paths = parameters.get("file_paths")
    file_paths = raw_paths if isinstance(raw_paths, list) else [parameters.get("file_path")]

    documents: list[dict[str, Any]] = []
    for raw_path in file_paths:
        path_value = coerce_text(raw_path).strip()
        if not path_value:
            continue
        path = _resolve_local_path(path_value)
        if not path.exists() or not path.is_file():
            raise ValueError(f"Document file not found: {path}")
        text_content, mime_type = _load_file_text(path)
        documents.append(
            _build_document(
                str(path),
                text_content,
                mime_type,
                {"extension": path.suffix.lower(), "file_name": path.name, "size_bytes": path.stat().st_size},
            )
        )

    if not documents:
        raise ValueError("DOCUMENT_LOADER requires at least one readable file")
    return {"documents": documents}


def _directory_loader_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    directory = _resolve_local_path(coerce_text(parameters.get("directory_path")).strip())
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory not found: {directory}")

    recursive = coerce_bool(parameters.get("recursive", True))
    include_extensions = parameters.get("include_extensions") or sorted(SUPPORTED_DOCUMENT_EXTENSIONS)
    if not isinstance(include_extensions, list):
        raise ValueError("include_extensions must be an array")
    extensions = {str(item).lower() for item in include_extensions}
    paths = directory.rglob("*") if recursive else directory.glob("*")

    documents: list[dict[str, Any]] = []
    for path in sorted(paths):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        text_content, mime_type = _load_file_text(path)
        documents.append(
            _build_document(
                str(path.resolve()),
                text_content,
                mime_type,
                {
                    "extension": path.suffix.lower(),
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(directory)),
                    "size_bytes": path.stat().st_size,
                },
            )
        )
    return {"documents": documents}


def _web_scraper_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    url = coerce_text(parameters.get("url")).strip()
    if not url:
        raise ValueError("WEB_SCRAPER requires a url")
    timeout_s = coerce_float(parameters.get("timeout_s"), 15.0)
    response = httpx.get(url, timeout=timeout_s, follow_redirects=True, headers={"User-Agent": "ParaGraph/1.0"})
    response.raise_for_status()
    raw_text = response.text
    text_content = _html_to_text(raw_text) if coerce_bool(parameters.get("strip_html_content", True)) else raw_text
    parsed = urlparse(str(response.url))
    document = _build_document(
        str(response.url),
        text_content,
        response.headers.get("content-type", "text/html").split(";")[0],
        {"host": parsed.netloc, "path": parsed.path or "/", "status_code": response.status_code},
    )
    return {"documents": [document]}


def _api_fetcher_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    parsed = ApiFetcherParameters.model_validate(parameters)
    targets = _coerce_api_targets(parsed)
    documents = (
        asyncio.run(_concurrent_fetch_api_documents(parsed, targets))
        if parsed.allow_concurrency and len(targets) > 1
        else _sync_fetch_api_documents(parsed, targets)
    )
    return {"documents": documents}


def _database_connection_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    parsed = DatabaseConnectionParameters.model_validate(parameters)
    database_url, connect_args = _build_database_url(parsed.model_dump(mode="json"))
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to connect to database: {exc}") from exc
    finally:
        engine.dispose()

    resolved_file_path = str(_resolve_local_path(parsed.file_path)) if parsed.engine == "sqlite" else None
    return {
        "connection": {
            "engine": parsed.engine,
            "database_name": parsed.database_name or (Path(resolved_file_path).stem if resolved_file_path else None),
            "host": parsed.host or None,
            "port": parsed.port,
            "username": parsed.username or None,
            "password": parsed.password or None,
            "file_path": resolved_file_path,
            "read_only": True,
            "options": {**parsed.options, "connect_timeout_s": parsed.connect_timeout_s},
        }
    }


def _database_query_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    connection_input = inputs.get("connection")
    if not isinstance(connection_input, dict):
        raise ValueError("DATABASE_QUERY requires a database connection input")

    query_text = _sanitize_query_text(coerce_text(parameters.get("query_text")))
    row_limit = max(1, coerce_int(parameters.get("row_limit"), 250))
    database_url, connect_args = _build_database_url(connection_input)
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)

    try:
        with engine.connect() as connection:
            result = connection.execute(text(query_text))
            rows = [dict(row._mapping) for row in result.fetchmany(row_limit)]
    except SQLAlchemyError as exc:
        raise ValueError(f"Database query failed: {exc}") from exc
    finally:
        engine.dispose()

    engine_name = str(connection_input.get("engine") or "database")
    database_name = str(connection_input.get("database_name") or connection_input.get("file_path") or "default")
    source_root = f"database://{engine_name}/{database_name}"
    documents = [
        _build_document(
            f"{source_root}#row={index}",
            json.dumps(row, indent=2, ensure_ascii=True, default=str),
            "application/json",
            {
                "row_index": index,
                "engine": engine_name,
                "database_name": database_name,
                "query_text": query_text,
            },
        )
        for index, row in enumerate(rows)
    ]
    return {"documents": documents, "records": rows}


INGESTION_HANDLERS = {
    "document_loader": NodeHandler(executor=_document_loader_executor, parameter_model=DocumentLoaderParameters),
    "directory_loader": NodeHandler(executor=_directory_loader_executor, parameter_model=DirectoryLoaderParameters),
    "web_scraper": NodeHandler(executor=_web_scraper_executor, parameter_model=WebScraperParameters),
    "api_fetcher": NodeHandler(executor=_api_fetcher_executor, parameter_model=ApiFetcherParameters),
    "database_connection": NodeHandler(executor=_database_connection_executor, parameter_model=DatabaseConnectionParameters),
    "database_query": NodeHandler(executor=_database_query_executor, parameter_model=DatabaseQueryParameters),
}
