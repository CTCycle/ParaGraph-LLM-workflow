# Nodes Library

This document is the reference for all currently implemented workflow nodes and their parameters.

Source of truth: `ParaGraph/resources/nodes/*.json`

## Custom Plugin Nodes

Custom nodes can be declared through a manifest plus a Python script:
- `runtime.plugin.script_path`: relative path from the manifest file to the script.
- `runtime.plugin.entrypoint`: callable function name (default `execute`).
- Entry point contract: `execute(parameters: dict, inputs: dict) -> dict`.

For cross-machine sharing, keep plugin scripts alongside the manifest (for example `plugins/my_node.py`) and avoid absolute paths.

## Connection Types

Node manifests support three connection collections:

- `inputs`: data dependencies consumed by node execution.
- `outputs`: data payloads produced by node execution.
- `controllers`: behavior/configuration control links (not part of regular data flow), with directional placement metadata (`scope`).

For all LLM nodes, the `model` link is a required `controller` with `scope: target` (single inbound model selection).

Controller placement contract:
- `scope: source` -> connector appears on the right edge (same lane as outputs).
- `scope: target` -> snap-point appears on the left edge (same lane as inputs).
- `scope: both` -> both source and target handles are rendered.
## Node Index

| Node ID | Version | Name | Category | Manifest |
|---|---:|---|---|---|
| `API_FETCHER` | 1 | API Fetcher | input | `api_fetcher_v1.json` |
| `BATCH_EMBEDDER` | 1 | Batch Embedder | model | `batch_embedder_v1.json` |
| `CHUNKER` | 1 | Chunker | processing | `chunker_v1.json` |
| `CONTEXT_INJECTOR` | 1 | Context Injector | processing | `context_injector_v1.json` |
| `DATABASE_CONNECTION` | 1 | Database Connection | input | `database_connection_v1.json` |
| `DATABASE_QUERY` | 1 | Database Query | input | `database_query_v1.json` |
| `DIRECTORY_LOADER` | 1 | Directory Loader | input | `directory_loader_v1.json` |
| `DOCUMENT_LOADER` | 1 | Document Loader | input | `document_loader_v1.json` |
| `EMBEDDING_MODEL` | 1 | Embedding Model | model | `embedding_model_v1.json` |
| `IF` | 1 | If | control | `if_v1.json` |
| `IMAGE_INPUT` | 1 | Image Input | input | `image_input_v1.json` |
| `IMAGE_OUTPUT` | 1 | Image Output | output | `image_output_v1.json` |
| `JSON_OUTPUT` | 1 | JSON Output | output | `json_output_v1.json` |
| `LLM_CHAT` | 1 | LLM Chat | model | `llm_chat_v1.json` |
| `LLM_STRUCTURED` | 1 | LLM Structured | model | `llm_structured_v1.json` |
| `LOAD_TEXT` | 1 | Load Text | serialization | `load_text_v1.json` |
| `MODEL_PROVIDER` | 1 | Model Provider | model | `model_provider_v1.json` |
| `ROUTER` | 1 | Router | control | `router_v1.json` |
| `SAVE_TEXT` | 1 | Save Text | serialization | `save_text_v1.json` |
| `SIMILARITY_SEARCH` | 1 | Similarity Search | processing | `similarity_search_v1.json` |
| `SYSTEM_PROMPT` | 1 | System Prompt | input | `system_prompt_v1.json` |
| `TEMPLATE_FORMAT` | 1 | Template Format | processing | `template_format_v1.json` |
| `TEXT_CLEANER` | 1 | Text Cleaner | processing | `text_cleaner_v1.json` |
| `TEXT_OUTPUT` | 1 | Text Output | output | `text_output_v1.json` |
| `TEXT_SPLIT` | 1 | Text Split | processing | `text_split_v1.json` |
| `TOKENIZE` | 1 | Tokenize | processing | `tokenize_v1.json` |
| `USER_PROMPT` | 1 | User Prompt | input | `user_prompt_v1.json` |
| `VECTOR_DB_WRITER` | 1 | Vector DB Writer | serialization | `vector_db_writer_v1.json` |
| `WEB_SCRAPER` | 1 | Web Scraper | input | `web_scraper_v1.json` |

---

## `MODEL_PROVIDER` (v1)

- Name: Model Provider
- Category: `model`
- Description: Select a provider and model, then expose a reusable typed model handle to connected LLM nodes.

Inputs: None.

Outputs: None.

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `model` | `MODEL_HANDLE` | No | `source` |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `provider` | `TEXT` | `ollama` | `select` | Yes | Model provider. |
| `model_name` | `TEXT` | `""` | `select` | Yes | Model identifier available for the selected provider. |

## `LLM_CHAT` (v1)

- Name: LLM Chat
- Category: `model`
- Description: Run a chat completion with a typed model handle selected by a provider node and return plain text.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `user_prompt` | `TEXT` | No |
| `system_prompt` | `TEXT` | No |
| `image` | `IMAGE` | No |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `response` | `TEXT` | Yes |

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `model` | `MODEL_HANDLE` | Yes | `target` (left) |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `context_window` | `JSON` | `0` | `number` | No | Context window size. Use `0` for provider-managed context. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable reasoning-oriented execution when the selected model supports it. |

## `LLM_STRUCTURED` (v1)

- Name: LLM Structured
- Category: `model`
- Description: Run a structured generation with a typed model handle selected by a provider node and return validated JSON.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `user_prompt` | `TEXT` | No |
| `system_prompt` | `TEXT` | No |
| `image` | `IMAGE` | No |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `result` | `JSON` | Yes |

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `model` | `MODEL_HANDLE` | Yes | `target` (left) |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `context_window` | `JSON` | `0` | `number` | No | Context window size. Use `0` for provider-managed context. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable reasoning-oriented execution when the selected model supports it. |
| `response_schema` | `JSON` | `{"type":"object","properties":{},"required":[]}` | `json` | Yes | JSON Schema used to validate the structured response. |

## `EMBEDDING_MODEL` (v1)

- Name: Embedding Model
- Category: `model`
- Description: Convert text into embedding vectors.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `embedding` | `EMBEDDING` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `provider` | `TEXT` | `ollama` | `select` | No | Provider name. |
| `model_name` | `TEXT` | `nomic-embed-text` | `text` | No | Embedding model identifier. |

## `IF` (v1)

- Name: If
- Category: `control`
- Description: Choose between two values based on a boolean input.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `condition` | `BOOLEAN` | Yes |
| `true_value` | `ANY` | Yes |
| `false_value` | `ANY` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `result` | `ANY` | Yes |

Parameters: None.

## `IMAGE_INPUT` (v1)

- Name: Image Input
- Category: `input`
- Description: Provide an image file path to the workflow graph.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `image` | `IMAGE` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `file_path` | `TEXT` | `""` | `text` | Yes | Path to the source image file. |

## `IMAGE_OUTPUT` (v1)

- Name: Image Output
- Category: `output`
- Description: Expose final image results.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `image` | `IMAGE` | Yes |

Outputs: None.

Parameters: None.

## `LOAD_TEXT` (v1)

- Name: Load Text
- Category: `serialization`
- Description: Load text content from a local file path.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `storage_path` | `TEXT` | `""` | `file` | No | Absolute local source file path. Relative paths remain rooted in ParaGraph/resources/artifacts for legacy workflows. |

## `ROUTER` (v1)

- Name: Router
- Category: `control`
- Description: Route a value to matched or unmatched output based on a parameter.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `value` | `ANY` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `matched` | `ANY` | No |
| `unmatched` | `ANY` | No |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `expected_value` | `TEXT` | `""` | `text` | No | Value to compare against. |

## `SAVE_TEXT` (v1)

- Name: Save Text
- Category: `serialization`
- Description: Persist text content to a local file path.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `artifact` | `JSON` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `storage_path` | `TEXT` | `""` | `file` | No | Absolute local destination file path. Relative paths remain rooted in ParaGraph/resources/artifacts for legacy workflows. |

## `SYSTEM_PROMPT` (v1)

- Name: System Prompt
- Category: `input`
- Description: Provide system-role instruction text to the workflow graph.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `prompt_text` | `TEXT` | `""` | `textarea` | Yes | Instruction text emitted as the system message. |

## `TEMPLATE_FORMAT` (v1)

- Name: Template Format
- Category: `processing`
- Description: Format text using a simple template.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `input` | `TEXT` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `template` | `TEXT` | `{input}` | `textarea` | No | Template string containing `{input}`. |

## `TEXT_OUTPUT` (v1)

- Name: Text Output
- Category: `output`
- Description: Expose final text results.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Outputs: None.

Parameters: None.

## `TEXT_SPLIT` (v1)

- Name: Text Split
- Category: `processing`
- Description: Split text into segments using a delimiter.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `segments` | `JSON` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `delimiter` | `TEXT` | `\n` | `text` | No | Delimiter used for splitting. |

## `TOKENIZE` (v1)

- Name: Tokenize
- Category: `processing`
- Description: Split text into token ids.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `tokens` | `TOKEN_IDS` | Yes |

Parameters: None.

## `USER_PROMPT` (v1)

- Name: User Prompt
- Category: `input`
- Description: Provide user-role prompt text to the workflow graph.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `prompt_text` | `TEXT` | `""` | `textarea` | Yes | Prompt text emitted as the user message. |

---

## Phase 1 RAG Payload Types

- `DOCUMENT_LIST`: normalized documents with `id`, `text`, `source_uri`, `mime_type`, and `metadata`.
- `DATABASE_CONNECTION`: read-only database connection manifest with engine-specific connection details.
- `CHUNK_LIST`: document chunks with `document_id`, `chunk_index`, `token_count`, and inherited metadata.
- `VECTOR_POINT_LIST`: embedded chunks plus vector values and embedding provider/model metadata.
- `VECTOR_STORE_HANDLE`: persisted vector store metadata for downstream retrieval nodes.
- `RETRIEVAL_RESULTS`: `{ query, hits[] }` payload used between retrieval and prompt-construction nodes.

## `DOCUMENT_LOADER` (v1)

- Name: Document Loader
- Category: `input`
- Description: Load one or more supported local documents into a normalized `DOCUMENT_LIST` payload.

Inputs: None.
Outputs: `documents: DOCUMENT_LIST`.
Parameters: `file_paths`.

## `DIRECTORY_LOADER` (v1)

- Name: Directory Loader
- Category: `input`
- Description: Load supported files from a directory into a normalized `DOCUMENT_LIST` payload.

Parameters: `directory_path`, `recursive`, `include_extensions`.

## `WEB_SCRAPER` (v1)

- Name: Web Scraper
- Category: `input`
- Description: Fetch one HTML page and emit plain-text content as `DOCUMENT_LIST`.

Parameters: `url`, `timeout_s`, `strip_html_content`.

## `API_FETCHER` (v1)

- Name: API Fetcher
- Category: `input`
- Description: Fetch HTTP JSON/text content from one or more endpoints and emit it as `DOCUMENT_LIST`.

Parameters: `url`, `request_urls`, `headers`, `timeout_s`, `response_selector`, `max_calls`, `allow_concurrency`.

## `DATABASE_CONNECTION` (v1)

- Name: Database Connection
- Category: `input`
- Description: Validate and emit a reusable read-only `DATABASE_CONNECTION` manifest for SQLite or PostgreSQL.

Inputs: None.
Outputs: `connection: DATABASE_CONNECTION`.
Parameters: `engine`, `file_path`, `host`, `port`, `database_name`, `username`, `password`, `options`, `connect_timeout_s`.

## `DATABASE_QUERY` (v1)

- Name: Database Query
- Category: `input`
- Description: Execute a single read-only SQL statement against a connected database and emit both normalized documents and raw records.

Inputs: `connection: DATABASE_CONNECTION`.
Outputs: `documents: DOCUMENT_LIST`, `records: JSON`.
Parameters: `query_text`, `row_limit`.

## `TEXT_CLEANER` (v1)

- Name: Text Cleaner
- Category: `processing`
- Description: Normalize document text while preserving metadata.

Inputs: `documents: DOCUMENT_LIST`.
Outputs: `documents: DOCUMENT_LIST`.
Parameters: `strip_html_content`, `collapse_whitespace`.

## `CHUNKER` (v1)

- Name: Chunker
- Category: `processing`
- Description: Convert `DOCUMENT_LIST` into `CHUNK_LIST` with configurable token sizing and overlap.

Parameters: `strategy`, `chunk_size_tokens`, `chunk_overlap_tokens`, `respect_sentence_boundaries`.

## `BATCH_EMBEDDER` (v1)

- Name: Batch Embedder
- Category: `model`
- Description: Convert `CHUNK_LIST` into `VECTOR_POINT_LIST` using the configured embedding provider/model.

Parameters: `provider`, `model_name`, `batch_size`, `dimensions`, `normalize`, `max_retries`.

## `VECTOR_DB_WRITER` (v1)

- Name: Vector DB Writer
- Category: `serialization`
- Description: Persist `VECTOR_POINT_LIST` into a local FAISS-backed store under a selected destination directory (or artifacts/vectorstores when omitted).

Outputs: `store: VECTOR_STORE_HANDLE`.
Parameters: `backend`, `index_name`, `storage_directory`, `metric`, `index_type`, `write_mode`, `nlist`, `hnsw_m`.

## `SIMILARITY_SEARCH` (v1)

- Name: Similarity Search
- Category: `processing`
- Description: Embed a query with the store metadata and return ranked `RETRIEVAL_RESULTS`.

Inputs: `query: TEXT`, `store: VECTOR_STORE_HANDLE`.
Outputs: `results: RETRIEVAL_RESULTS`.
Parameters: `top_k`, `score_threshold`, `filter`, `include_metadata`.

## `CONTEXT_INJECTOR` (v1)

- Name: Context Injector
- Category: `processing`
- Description: Convert `RETRIEVAL_RESULTS` into prompt-ready `TEXT` with optional citations.

Parameters: `max_context_items`, `include_citations`, `separator`.

## `JSON_OUTPUT` (v1)

- Name: JSON Output
- Category: `output`
- Description: Expose final structured JSON results.

Inputs: `value: JSON`.
Outputs: None.


