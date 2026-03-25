from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader
from sqlalchemy import URL, create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ParaGraph.server.domain.node_handler_ingestion import (
    DirectoryLoaderParameters,
    DatabaseConnectionParameters,
    LOAD_DOCUMENTS_SUPPORTED_EXTENSIONS,
    LoadDocumentsParameters,
    SQLDatabaseParameters,
    SQLFileDatabaseParameters,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    normalize_database_engine,
)
from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import (
    coerce_bool,
    coerce_int,
    coerce_text,
)


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


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _load_doc_text_fallback(path: Path) -> str:
    # Legacy .doc extraction fallback: preserve printable text when a binary parser is unavailable.
    raw = path.read_bytes()
    for encoding in ("utf-8", "latin-1"):
        decoded = raw.decode(encoding, errors="ignore")
        compact = "\n".join(line.strip() for line in decoded.splitlines() if line.strip())
        if compact:
            return compact
    return ""


def _load_file_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return _read_text_file(path), mimetypes.guess_type(str(path))[0] or "text/plain"
    if suffix in {".html", ".htm"}:
        raw = _read_text_file(path)
        return _html_to_text(raw), mimetypes.guess_type(str(path))[0] or "text/html"
    if suffix == ".json":
        payload = json.loads(_read_text_file(path))
        text_payload = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=True, default=str)
        return text_payload, "application/json"
    if suffix in {".csv", ".tsv", ".log", ".xml", ".yaml", ".yml"}:
        return _read_text_file(path), mimetypes.guess_type(str(path))[0] or "text/plain"
    if suffix == ".rtf":
        return _read_text_file(path), "application/rtf"
    if suffix == ".doc":
        extracted = _load_doc_text_fallback(path)
        if not extracted.strip():
            raise ValueError(f"Unable to extract readable text from legacy .doc file: {path}")
        return extracted, "application/msword"
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


def _build_database_url(payload: dict[str, Any]) -> tuple[str | URL, dict[str, Any]]:
    engine = normalize_database_engine(payload.get("engine"), label="engine")
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
        raise ValueError(f"{engine} connections require host, database_name, username, and port")

    query = {str(key): str(value) for key, value in options.items()}
    driver = "postgresql+psycopg" if engine == "postgresql" else "mysql+pymysql"
    return (
        URL.create(
            driver,
            username=username,
            password=password or None,
            host=host,
            port=int(port),
            database=database_name,
            query=query,
        ),
        {"connect_timeout": coerce_int(payload.get("connect_timeout_s"), 5)},
    )


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


def _load_documents_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    parsed = LoadDocumentsParameters.model_validate(parameters)
    directory = _resolve_local_path(parsed.folder_path)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory not found: {directory}")

    paths = directory.rglob("*") if parsed.recursive else directory.glob("*")
    documents: list[dict[str, Any]] = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        extension = path.suffix.lower()
        if extension not in LOAD_DOCUMENTS_SUPPORTED_EXTENSIONS:
            continue
        resolved = str(path.resolve())
        documents.append(
            _build_document(
                resolved,
                "",
                mimetypes.guess_type(resolved)[0] or "text/plain",
                {
                    "extension": extension,
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(directory)),
                    "size_bytes": path.stat().st_size,
                    "deferred_load": True,
                    "file_path": resolved,
                },
            )
        )
    return {"documents": documents}


def _build_sql_connection_options(*, db_ssl: bool, db_ssl_ca: str) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if db_ssl:
        options["ssl"] = "true"
        if db_ssl_ca.strip():
            options["ssl_ca"] = db_ssl_ca.strip()
    return options


def _sql_database_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    parsed = SQLDatabaseParameters.model_validate(parameters)
    connection_payload = {
        "engine": parsed.db_engine,
        "database_name": parsed.db_name,
        "host": parsed.db_host,
        "port": parsed.db_port,
        "username": parsed.db_user,
        "password": parsed.db_password,
        "file_path": "",
        "options": _build_sql_connection_options(db_ssl=parsed.db_ssl, db_ssl_ca=parsed.db_ssl_ca),
        "connect_timeout_s": parsed.db_connect_timeout,
    }
    return _validate_and_build_database_connection(connection_payload)


def _sql_file_database_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    parsed = SQLFileDatabaseParameters.model_validate(parameters)
    connection_payload = {
        "engine": parsed.db_engine,
        "database_name": parsed.db_name,
        "host": "",
        "port": parsed.db_port,
        "username": parsed.db_user,
        "password": parsed.db_password,
        "file_path": parsed.db_path,
        "options": _build_sql_connection_options(db_ssl=parsed.db_ssl, db_ssl_ca=parsed.db_ssl_ca),
        "connect_timeout_s": parsed.db_connect_timeout,
    }
    return _validate_and_build_database_connection(connection_payload)


def _validate_and_build_database_connection(parameters: dict[str, Any]) -> dict[str, Any]:
    parsed = DatabaseConnectionParameters.model_validate(parameters)
    database_url, connect_args = _build_database_url(parsed.model_dump(mode="json"))
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    try:
        with Session(engine) as db_session:
            db_session.execute(select(1)).scalar_one()
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


INGESTION_HANDLERS = {
    "directory_loader": NodeHandler(executor=_directory_loader_executor, parameter_model=DirectoryLoaderParameters),
    "load_documents": NodeHandler(executor=_load_documents_executor, parameter_model=LoadDocumentsParameters),
    "sql_database": NodeHandler(executor=_sql_database_executor, parameter_model=SQLDatabaseParameters),
    "sql_file_database": NodeHandler(executor=_sql_file_database_executor, parameter_model=SQLFileDatabaseParameters),
}

