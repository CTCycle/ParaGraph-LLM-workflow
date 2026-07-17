# Processing And Retrieval
Last updated: 2026-07-17

## Similarity Search Contract
- `search_mode`
  - `vector`, `keyword`, `hybrid`
- `search_engine`
  - `native`, `faiss_augmented`
- `similarity_strategy`
  - `cosine`, `euclidean`, `dot`

## Named Variables From JSON
When a connected node output is a JSON object, or a JSON string that parses to a JSON object, ParaGraph publishes each top-level key as a downstream named variable. Nested keys and array indexes are not published automatically.

If a source node also sets `__output_name`, that alias remains available for backward compatibility. When the alias collides with a top-level JSON key, the alias wins and the original JSON fields remain available under `__json_fields__`.

Example structured output:

```json
{
  "summary": "The trial met its primary endpoint.",
  "keywords": ["phase 2", "safety", "efficacy"]
}
```

Template and prompt formatting can reference those fields directly:

```jinja
Summary: {{ summary }}
Keywords: {{ keywords | join(", ") }}
```

HTTP nodes can also use named variables in query parameters or request body templates, or receive a full upstream JSON object as the request body.

## Prompt And Structured JSON Nodes
- `PROMPT_TEMPLATE` is presented as Template and Prompt Format.
- It supports Jinja syntax, including `system_template`, `user_template`, `reusable_blocks`, and strict missing-variable validation.
- Prompt templates use Jinja syntax only; legacy `{name}` formatting is not supported.
- `LLM_STRUCTURED` handles structured generation and extraction.
- It returns the main JSON object as `result` plus `schema`, `valid`, and `errors`.
- Validation can use JSON Schema mode, an inferred model, or pasted Pydantic model source parsed without executing arbitrary Python.
- Related structured nodes include `STRUCTURED_INPUT`, `STRUCTURED_OUTPUT`, and `OUTPUT_PARSER`.

## RAG And Document Processing
- Primary document and retrieval extension points are:
  - Load Documents
  - Document Text Extractor
  - Text Embedding
  - Vector Store
  - Similarity Search
  - Rerank Results
- Additional RAG nodes include:
  - `HTML_TO_TEXT`
  - `CHUNK_ENRICHER`
  - `CONTEXT_BUILDER`
  - `CITATION_FORMATTER`

## Text Processing And Advanced Text
Processing coverage includes normalization, regex extraction and replacement, join and merge, deduplication, metadata attachment, claim extraction, contradiction detection, entity extraction and resolution, PII detection and redaction, prompt injection detection, instruction stripping, diffing, table extraction, Markdown parsing, code block extraction, citation extraction, date normalization, and unit and number normalization.

Nodes that previously advertised model-backed, tokenizer-backed, OCR, repair,
dynamic routing, subgraph mapping, batching, or fallback behavior without
implementing those contracts were removed from the production catalog. They
must return as new versioned nodes only with real runtime implementations.

Representative newer manifests include:
- Processing:
  - `NORMALIZE_TEXT`
  - `REGEX_EXTRACT`
  - `REGEX_REPLACE`
  - `JOIN_MERGE_TEXT`
  - `DEDUPLICATE_TEXT`
  - `METADATA_ATTACH`
- Advanced text:
  - `CLAIM_EXTRACTOR`
  - `CONTRADICTION_DETECTOR`
  - `ENTITY_EXTRACTOR`
  - `ENTITY_RESOLVER`
  - `PII_DETECTOR`
  - `PII_REDACTOR`
  - `PROMPT_INJECTION_DETECTOR`
  - `INSTRUCTION_STRIPPER`
  - `DIFF_TEXT`
  - `TABLE_EXTRACTOR`
  - `MARKDOWN_PARSER`
  - `CODE_BLOCK_EXTRACTOR`
  - `CITATION_EXTRACTOR`
  - `DATE_NORMALIZER`
  - `UNIT_NUMBER_NORMALIZER`

## Web API Nodes
- HTTP GET, POST, PUT, PATCH, and DELETE nodes use the backend `httpx` client.
- Only `http` and `https` schemes are allowed.
- Hostnames are resolved before requests and loopback, private, link-local, multicast, and unspecified addresses are blocked by default.
- `PARAGRAPH_ALLOW_PRIVATE_HTTP_NODES=true` should only be enabled in trusted local environments when private targets are required.
- Sensitive headers such as `authorization`, `cookie`, `set-cookie`, and `x-api-key` are redacted in traces.

## Control, Tokenizer, Metadata, And Vector Search
- Control nodes include `IF_TEXT_CONTAINS`, `REDUCE_CHUNKS`, `CACHE_NODE`, `HUMAN_REVIEW_GATE`, and `TRACE_DEBUG_VIEWER`.
- Execution state supports `skipped` steps and `paused` runs for human review workflows.
- `TOKENIZER` version 2 tokenizes text, documents, document lists, chunks, and chunk lists through Hugging Face `AutoTokenizer.from_pretrained`.
- It preserves input order and emits structured `TOKENIZER_OUTPUT` or serialized text.
- `METADATA` attaches structured metadata to `DOCUMENT`, `DOCUMENT_LIST`, `CHUNK`, and `CHUNK_LIST` payloads with merge or replace behavior.
- `VECTOR_STORE` hides backend-specific collection, metadata, indexing, and search behavior behind the vector store adapter interface.
- Vector store handles include backend, collection or index, metric, dimension, embedding provider and model, and index metadata.
- `SIMILARITY_SEARCH` validates vector store metric and embedding source before search, and only forwards metadata filters or hybrid mode when the backend advertises support.
