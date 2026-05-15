from __future__ import annotations

import json
from typing import Any

from transformers import AutoTokenizer

from server.domain.node_handler_core import TokenizerParameters
from server.services.workflow.node_handlers.common import coerce_text

_TOKENIZER_CACHE: dict[tuple[str, str, bool], Any] = {}

###############################################################################
def _load_tokenizer(tokenizer_name: str, revision: str, use_fast: bool) -> Any:
    cache_key = (tokenizer_name, revision, use_fast)
    if cache_key not in _TOKENIZER_CACHE:
        kwargs: dict[str, Any] = {"use_fast": use_fast}
        if revision:
            kwargs["revision"] = revision
        _TOKENIZER_CACHE[cache_key] = AutoTokenizer.from_pretrained(
            tokenizer_name, **kwargs
        )
    return _TOKENIZER_CACHE[cache_key]

###############################################################################
def _payload_text(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("text", "content", "chunk"):
            value = payload.get(key)
            if value is not None:
                return coerce_text(value)
    return coerce_text(payload)

###############################################################################
def _payload_id(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("id", "chunk_id", "document_id", "source_uri"):
            value = coerce_text(payload.get(key) or "").strip()
            if value:
                return value
    return fallback

###############################################################################
def _collect_tokenizer_inputs(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if inputs.get("text") is not None:
        records.append(
            {"source_type": "text", "source_id": "text", "text": _payload_text(inputs["text"])}
        )
    for name, source_type in (("document", "document"), ("chunk", "chunk")):
        payload = inputs.get(name)
        if payload is not None:
            records.append(
                {
                    "source_type": source_type,
                    "source_id": _payload_id(payload, source_type),
                    "text": _payload_text(payload),
                }
            )
    for name, source_type in (("documents", "document"), ("chunks", "chunk")):
        payloads = inputs.get(name) if isinstance(inputs.get(name), list) else []
        for index, payload in enumerate(payloads, start=1):
            records.append(
                {
                    "source_type": source_type,
                    "source_id": _payload_id(payload, f"{source_type}:{index}"),
                    "text": _payload_text(payload),
                }
            )
    return [record for record in records if record["text"].strip()]

###############################################################################
def _tokenize_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = TokenizerParameters.model_validate(parameters)
    source_records = _collect_tokenizer_inputs(inputs)
    if not source_records:
        raise ValueError("TOKENIZER requires text, document, documents, chunk, or chunks input")

    tokenizer = _load_tokenizer(
        parsed.tokenizer_name, parsed.revision.strip(), bool(parsed.use_fast)
    )
    tokenizer_kwargs: dict[str, Any] = {
        "add_special_tokens": bool(parsed.add_special_tokens),
        "truncation": bool(parsed.truncation),
        "padding": parsed.padding,
        "return_attention_mask": bool(parsed.return_attention_mask),
        "return_token_type_ids": bool(parsed.return_token_type_ids),
    }
    if parsed.max_length > 0:
        tokenizer_kwargs["max_length"] = int(parsed.max_length)

    tokenized_records: list[dict[str, Any]] = []
    for record in source_records:
        encoded = tokenizer(record["text"], **tokenizer_kwargs)
        payload = dict(encoded)
        tokenized_records.append(
            {
                "source_type": record["source_type"],
                "source_id": record["source_id"],
                "text": record["text"],
                "token_ids": list(payload.get("input_ids", [])),
                "attention_mask": payload.get("attention_mask"),
                "token_type_ids": payload.get("token_type_ids"),
            }
        )

    structured = {
        "tokenizer_name": parsed.tokenizer_name,
        "revision": parsed.revision.strip(),
        "records": tokenized_records,
    }
    if parsed.output_format == "string":
        return {"serialized": json.dumps(structured, ensure_ascii=False)}
    if parsed.output_format == "json" or len(tokenized_records) != 1:
        return {"tokenized": structured}
    return {"tokens": tokenized_records[0]["token_ids"], "tokenized": structured}

###############################################################################
def _text_split_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    text = coerce_text(inputs.get("text") or "")
    delimiter = coerce_text(parameters.get("delimiter") or "\n")
    return {
        "segments": [
            segment.strip() for segment in text.split(delimiter) if segment.strip()
        ]
    }

###############################################################################
def _if_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    return {
        "result": inputs.get("true_value")
        if bool(inputs.get("condition"))
        else inputs.get("false_value")
    }

###############################################################################
def _router_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    value = inputs.get("value")
    expected = coerce_text(parameters.get("expected_value") or "")
    if coerce_text(value) == expected:
        return {"matched": value, "unmatched": None}
    return {"matched": None, "unmatched": value}


__all__ = [
    "_if_executor",
    "_router_executor",
    "_text_split_executor",
    "_tokenize_executor",
]

