from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from server.common.utils.values import coerce_text
from server.contracts.node_handler_rag import RagParameters
from server.services.workflow.nodes.handler import NodeHandler

###############################################################################
def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

###############################################################################
def _text(item: Any) -> str:
    if isinstance(item, dict):
        return coerce_text(
            item.get("text") or item.get("content") or item.get("chunk") or ""
        )
    return coerce_text(item)

###############################################################################
def _strip_html(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())

###############################################################################
def _html_to_text_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    return {"result": _strip_html(_text(inputs.get("html", inputs.get("text", ""))))}

###############################################################################
def _chunk_enricher_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    chunks = _items(inputs.get("chunks", inputs.get("value", [])))
    enriched = []
    for index, chunk in enumerate(chunks):
        record = dict(chunk) if isinstance(chunk, dict) else {"text": _text(chunk)}
        metadata = dict(record.get("metadata", {}))
        metadata.update(
            {
                "previous_chunk": _text(chunks[index - 1]) if index else "",
                "next_chunk": _text(chunks[index + 1])
                if index + 1 < len(chunks)
                else "",
            }
        )
        record["metadata"] = metadata
        enriched.append(record)
    return {"chunks": enriched}

###############################################################################
def _context_builder_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = RagParameters.model_validate(parameters)
    words: list[str] = []
    for item in _items(inputs.get("chunks", inputs.get("results", []))):
        for word in _text(item).split():
            if len(words) >= parsed.token_budget:
                break
            words.append(word)
    return {"result": " ".join(words)}

###############################################################################
def _citation_formatter_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    citations = []
    for item in _items(inputs.get("chunks", inputs.get("results", []))):
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
        citations.append(
            {
                key: metadata.get(key)
                for key in ("source", "page", "page_number", "line", "chunk_id")
            }
        )
    return {"result": citations}

###############################################################################
RAG_HANDLERS = {
    "html_to_text": NodeHandler(executor=_html_to_text_executor),
    "chunk_enricher": NodeHandler(executor=_chunk_enricher_executor),
    "context_builder": NodeHandler(
        executor=_context_builder_executor, parameter_model=RagParameters
    ),
    "citation_formatter": NodeHandler(executor=_citation_formatter_executor),
}
