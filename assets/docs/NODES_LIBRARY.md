# NODES_LIBRARY

Last updated: 2026-05-17

## Purpose

This document describes the node system used by ParaGraph workflows, how nodes are cataloged, and how custom node manifests are imported.

## Node Catalog Sources

- Built-in node manifests are loaded from `app/resources/nodes`.
- Custom node manifests can be imported at runtime from the Nodes page (`/nodes`) using JSON payloads.
- The backend catalog API is `GET /nodes/catalog`.

## Core Node Categories

The frontend and backend organize nodes by category (for example):

- `input`
- `web`
- `prompt`
- `model`
- `memory`
- `retrieval`
- `embeddings`
- `processing`
- `text_segmentation`
- `output`
- `serialization`
- `database`
- `vector_storage`
- `control`

Category labels and ordering are defined in `app/client/src/workflow/schema/nodeCategory.ts`.

## Node Manifest Model

A node manifest includes:

- Identity: `id`, `version`, `name`, `category`, `description`
- Interface: `inputs`, `outputs`, optional `controllers`
- Parameters: typed parameter definitions and optional constraints/defaults
- UI metadata: visual defaults such as width/accent/icon/collapsed state
- Runtime metadata: executor key, cacheability, determinism, side effects, and optional plugin metadata

Runtime validation occurs through backend node registry logic before use in execution plans.

## Similarity Search Contract

- `search_mode`
  - options: `vector`, `keyword`, `hybrid`
- `search_engine`
  - options: `native`, `faiss_augmented`
- `similarity_strategy`
  - options: `cosine`, `euclidean`, `dot`

## Processing and Retrieval Nodes

## Named Variables from JSON

When a connected node output is a JSON object, or a JSON string that parses to a
JSON object, ParaGraph publishes each top-level key as a downstream named
variable. Nested keys and array indexes are not published automatically.

If a source node also sets `__output_name`, the alias remains available for
backward compatibility. When the alias collides with a JSON top-level key, the
alias wins and the original JSON fields remain available under
`__json_fields__`.

Example structured output:

```json
{
  "summary": "The trial met its primary endpoint.",
  "keywords": ["phase 2", "safety", "efficacy"]
}
```

Template / Prompt Format can reference those fields directly:

```jinja
Summary: {{ summary }}
Keywords: {{ keywords | join(", ") }}
```

HTTP nodes can use named variables in query parameters or request body templates,
and can also receive a full upstream JSON object as the body.

### Template / Prompt Format

`PROMPT_TEMPLATE` is displayed as Template / Prompt Format. It supports Jinja
syntax by default, including `system_template`, `user_template`,
`reusable_blocks`, and strict missing-variable validation. Legacy `{name}` format
templates remain supported for existing workflows.

### Structured JSON

`LLM_STRUCTURED` is the structured generation and extraction node. It returns the
main JSON object as `result` plus `schema`, `valid`, and `errors`. Validation can
use the existing JSON Schema mode, an inferred model, or a pasted Pydantic model
source parsed without executing arbitrary Python.

Additional structured nodes include Structured Input, Structured Output, JSON
Validate / Repair, and Output Parser.

### RAG and Document Processing

Existing document and retrieval nodes remain the primary extension points:
Load Documents covers document loading, Document Text Extractor covers text
extraction, Text Embedding covers embeddings, Vector Store covers upsert, Similarity
Search covers retrieval, and Rerank Results covers reranking.

Additional RAG nodes include HTML to Text, OCR Text Extract, Chunk Enricher,
Context Builder, Citation Formatter, and Grounding Checker. OCR returns a clear
`ocr_engine_unavailable` error when the host does not provide the `tesseract`
executable.

### Text Processing and Advanced Text

Processing nodes now include normalization, regex extract/replace, token and
semantic splitting, join/merge, deduplication, metadata attach, language detect,
token counter, truncation, summarize, rewrite, claim extraction, contradiction
detection, entity extraction/resolution, PII detection/redaction, prompt injection
detection, instruction stripping, diff, patch apply, table extraction, Markdown
parsing, code block extraction, citation extraction, date normalization,
unit/number normalization, classifier scaffolds, quality scoring, and compression.

### Web API Nodes

HTTP GET, POST, PUT, PATCH, and DELETE nodes use the backend `httpx` client. They
allow only `http` and `https`, resolve hostnames before requests, and block
loopback, private, link-local, multicast, and unspecified addresses by default.
Set `PARAGRAPH_ALLOW_PRIVATE_HTTP_NODES=true` only in trusted local environments
when private targets are required. Sensitive headers such as `authorization`,
`cookie`, `set-cookie`, and `x-api-key` are redacted in traces.

### Workflow Control

Control nodes include If Text Contains, Switch by Label, Map over Chunks, Reduce
Chunks, Batch Processor, Cache Node, Human Review Gate, Error Fallback, and Trace
/ Debug Viewer. Execution state supports `skipped` steps and `paused` runs for
human review workflows.

### Tokenizer

`TOKENIZER` version 2 tokenizes text, documents, document lists, chunks, and chunk lists through Hugging Face `AutoTokenizer.from_pretrained`. It preserves input order and emits structured `TOKENIZER_OUTPUT` or serialized text.

### Metadata

`METADATA` attaches structured metadata to `DOCUMENT`, `DOCUMENT_LIST`, `CHUNK`, and `CHUNK_LIST` payloads. It supports merge or replace behavior, global metadata, and per-record metadata keyed by an ID field.

### Vector Store and Vector Collection

`VECTOR_STORE` keeps backend-specific collection, metadata, indexing, and search behavior behind the vector store adapter interface. Handles include backend, collection/index, metric, dimension, embedding provider/model, and index metadata. Backends expose capabilities such as metadata filtering, hybrid search, and FAISS augmentation through `describe_capabilities`.

### Similarity Search

`SIMILARITY_SEARCH` validates the connected vector store metric and embedding source before search. Metadata filters are passed to backends only when supported, and hybrid mode requires a backend that advertises hybrid search support.

## Database Nodes

The database category includes SQL database connection nodes, CRUD create/read/update/delete nodes, and a custom SQL query node. Existing SQL nodes use typed database connection controllers and parameterized SQLAlchemy execution paths.

## Tool Nodes

### Tool Collection

`TOOL_COLLECTION` creates a typed `TOOL_COLLECTION_HANDLE` from inline Python functions, JSON schema tool definitions, signature text, or local `.py` files. Callable signatures are converted into JSON schema parameter definitions.

### Tool Call

`TOOL_CALL` is provider-neutral. It accepts a `MODEL_HANDLE` from `MODEL_PROVIDER` and a `TOOL_COLLECTION_HANDLE`, uses native tool calling when a provider advertises support, and falls back to structured JSON selection otherwise. It is designed for Ollama, Hugging Face, OpenAI, Gemini, and future providers that implement the provider service interface.

## Importing Custom Nodes

### API

- Endpoint: `POST /nodes/import`
- Request body: node manifest JSON
- Response: imported manifest
- Validation failures return HTTP 422

### UI flow

- Open `/nodes`
- Use the custom node import modal
- Paste/validate manifest JSON
- Submit import
- Reload catalog to make the node available in the workflow editor

## Workflow Integration

- Workflow editor (`/`) fetches the catalog and allows drag/drop node placement.
- Compiler validates node existence, version, ports/controllers compatibility, and required inputs.
- Execution resolves node handlers by manifest metadata through the registry.

## Connectivity Checks

Node-level connectivity endpoints:

- `POST /nodes/check-database-connection`
- `POST /nodes/check-vector-store-connection`

These are used by database/vector-store nodes to validate runtime connection settings before execution.

## Operational Notes

- Node manifests are contract-critical: changes to IDs, versions, or ports affect existing workflows.
- Prefer introducing new versions instead of breaking existing version semantics.
- Keep manifest descriptions explicit so the Nodes page remains understandable to end users.

## Newly Added Manifests

- Structured JSON: `STRUCTURED_INPUT`, `STRUCTURED_OUTPUT`, `JSON_VALIDATE_REPAIR`, `OUTPUT_PARSER`
- RAG: `HTML_TO_TEXT`, `OCR_TEXT_EXTRACT`, `CHUNK_ENRICHER`, `CONTEXT_BUILDER`, `CITATION_FORMATTER`, `GROUNDING_CHECKER`
- Processing: `NORMALIZE_TEXT`, `REGEX_EXTRACT`, `REGEX_REPLACE`, `TOKEN_SPLIT_CHUNKS`, `SEMANTIC_SPLIT_CHUNKS`, `JOIN_MERGE_TEXT`, `DEDUPLICATE_TEXT`, `METADATA_ATTACH`, `LANGUAGE_DETECT`, `TOKEN_COUNTER`, `TRUNCATE_TO_BUDGET`, `LLM_SUMMARIZE`, `LLM_REWRITE`
- Advanced text: `CLAIM_EXTRACTOR`, `CONTRADICTION_DETECTOR`, `ENTITY_EXTRACTOR`, `ENTITY_RESOLVER`, `PII_DETECTOR`, `PII_REDACTOR`, `TOXICITY_POLICY_CLASSIFIER`, `PROMPT_INJECTION_DETECTOR`, `INSTRUCTION_STRIPPER`, `DIFF_TEXT`, `PATCH_APPLY`, `TABLE_EXTRACTOR`, `MARKDOWN_PARSER`, `CODE_BLOCK_EXTRACTOR`, `CITATION_EXTRACTOR`, `DATE_NORMALIZER`, `UNIT_NUMBER_NORMALIZER`, `SENTIMENT_INTENT_CLASSIFIER`, `TOPIC_CLASSIFIER`, `QUALITY_SCORER`, `COMPRESSION`
- Web API: `HTTP_GET`, `HTTP_POST`, `HTTP_PUT`, `HTTP_PATCH`, `HTTP_DELETE`
- Control: `IF_TEXT_CONTAINS`, `SWITCH_BY_LABEL`, `MAP_OVER_CHUNKS`, `REDUCE_CHUNKS`, `BATCH_PROCESSOR`, `CACHE_NODE`, `HUMAN_REVIEW_GATE`, `ERROR_FALLBACK`, `TRACE_DEBUG_VIEWER`

