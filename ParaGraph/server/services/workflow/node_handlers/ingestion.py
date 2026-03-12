from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid5, NAMESPACE_URL

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader
from pydantic import BaseModel, Field, field_validator

from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import coerce_bool, coerce_float, coerce_text, parse_json_value


SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".pdf", ".docx"}


class DocumentLoaderParameters(BaseModel):
    file_path: str


class DirectoryLoaderParameters(BaseModel):
    directory_path: str
    recursive: bool = True
    include_extensions: list[str] = Field(default_factory=lambda: sorted(SUPPORTED_DOCUMENT_EXTENSIONS))

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


class ApiFetcherParameters(BaseModel):
    url: str
    timeout_s: float = Field(default=15.0, ge=1.0, le=120.0)
    response_selector: str = ""


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
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages if (page.extract_text() or "").strip())


def _load_file_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8"), mimetypes.guess_type(str(path))[0] or "text/plain"
    if suffix in {".html", ".htm"}:
        raw = path.read_text(encoding="utf-8")
        return _html_to_text(raw), mimetypes.guess_type(str(path))[0] or "text/html"
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=True)
        return text, "application/json"
    if suffix == ".pdf":
        return _load_pdf_text(path), "application/pdf"
    if suffix == ".docx":
        return _load_docx_text(path), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise ValueError(f"Unsupported document type: {path.suffix or path.name}")


def _build_document(source_uri: str, text: str, mime_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _make_document_id(source_uri),
        "text": text.strip(),
        "source_uri": source_uri,
        "mime_type": mime_type,
        "metadata": metadata,
    }


def _document_loader_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    path = Path(coerce_text(parameters.get("file_path")).strip())
    if not path.exists() or not path.is_file():
        raise ValueError(f"Document file not found: {path}")
    text, mime_type = _load_file_text(path)
    document = _build_document(
        str(path.resolve()),
        text,
        mime_type,
        {"extension": path.suffix.lower(), "file_name": path.name, "size_bytes": path.stat().st_size},
    )
    return {"documents": [document]}


def _directory_loader_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    directory = Path(coerce_text(parameters.get("directory_path")).strip())
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
        text, mime_type = _load_file_text(path)
        documents.append(
            _build_document(
                str(path.resolve()),
                text,
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
    text = _html_to_text(raw_text) if coerce_bool(parameters.get("strip_html_content", True)) else raw_text
    parsed = urlparse(str(response.url))
    document = _build_document(
        str(response.url),
        text,
        response.headers.get("content-type", "text/html").split(";")[0],
        {"host": parsed.netloc, "path": parsed.path or "/", "status_code": response.status_code},
    )
    return {"documents": [document]}


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


def _api_fetcher_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    url = coerce_text(parameters.get("url")).strip()
    if not url:
        raise ValueError("API_FETCHER requires a url")
    timeout_s = coerce_float(parameters.get("timeout_s"), 15.0)
    response = httpx.get(url, timeout=timeout_s, follow_redirects=True, headers={"Accept": "application/json, text/plain;q=0.9, */*;q=0.8"})
    response.raise_for_status()
    content_type = response.headers.get("content-type", "application/json").split(";")[0]
    if content_type == "application/json":
        payload = response.json()
        selector = coerce_text(parameters.get("response_selector")).strip()
        selected = _select_json_value(payload, selector) if selector else payload
        text = selected if isinstance(selected, str) else json.dumps(selected, indent=2, ensure_ascii=True)
    else:
        text = response.text
    document = _build_document(
        str(response.url),
        text,
        content_type,
        {"host": urlparse(str(response.url)).netloc, "status_code": response.status_code},
    )
    return {"documents": [document]}


INGESTION_HANDLERS = {
    "document_loader": NodeHandler(executor=_document_loader_executor, parameter_model=DocumentLoaderParameters),
    "directory_loader": NodeHandler(executor=_directory_loader_executor, parameter_model=DirectoryLoaderParameters),
    "web_scraper": NodeHandler(executor=_web_scraper_executor, parameter_model=WebScraperParameters),
    "api_fetcher": NodeHandler(executor=_api_fetcher_executor, parameter_model=ApiFetcherParameters),
}
