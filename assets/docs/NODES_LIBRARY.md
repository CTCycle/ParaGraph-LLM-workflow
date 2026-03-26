# Nodes Library

This document is the reference for all currently implemented workflow nodes and their parameters.

Source of truth: `ParaGraph/resources/nodes/*.json`

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

## Categories

The node category set remains:

- `input`
- `model`
- `processing` (reserved; no built-in processing nodes in the current library)
- `fragmentation`
- `output`
- `serialization`
- `control`

## Node Index

| Node ID | Version | Name | Category | Manifest |
|---|---:|---|---|---|
| `BY_DELIMITER_CHUNKS` | 1 | By Delimiter Chunks | fragmentation | `by_delimiter_chunks_v1.json` |
| `BY_STRUCTURE_CHUNKS` | 1 | By Structure Chunks | fragmentation | `by_structure_chunks_v1.json` |
| `FIXED_SIZE_CHUNKS` | 1 | Fixed Size Chunks | fragmentation | `fixed_size_chunks_v1.json` |
| `JSON_OUTPUT` | 1 | JSON Output | output | `json_output_v1.json` |
| `LLM_CHAT` | 1 | LLM Chat | model | `llm_chat_v1.json` |
| `LLM_STRUCTURED` | 1 | LLM Structured | model | `llm_structured_v1.json` |
| `LOAD_DOCUMENTS` | 1 | Load Documents | serialization | `load_documents_v1.json` |
| `LOAD_TEXT` | 1 | Load Text | serialization | `load_text_v1.json` |
| `MERGE_SMALL_CHUNKS` | 1 | Merge Small Chunks | fragmentation | `merge_small_chunks_v1.json` |
| `MODEL_PROVIDER` | 1 | Model Provider | model | `model_provider_v1.json` |
| `PROMPT` | 1 | Prompt | input | `prompt_v1.json` |
| `RECURSIVE_SPLIT_CHUNKS` | 1 | Recursive Split Chunks | fragmentation | `recursive_split_chunks_v1.json` |
| `SAVE_TEXT` | 1 | Save Text | serialization | `save_text_v1.json` |
| `SENTENCE_WINDOW_CHUNKS` | 1 | Sentence Window Chunks | fragmentation | `sentence_window_chunks_v1.json` |
| `SQL_DATABASE` | 1 | SQL Database | control | `sql_database_v1.json` |
| `SQL_FILE_DATABASE` | 1 | Embedded SQL Database | control | `sql_file_database_v1.json` |
| `TEXT_OUTPUT` | 1 | Text Output | output | `text_output_v1.json` |

---

## `MODEL_PROVIDER` (v1)

- Name: Model Provider
- Category: `model`
- Description: Select a provider and model, then expose a reusable typed model handle to connected LLM nodes.

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `model` | `MODEL_HANDLE` | No | `source` |

Parameters:

| Name | Data Type | Default | UI Control | Required |
|---|---|---|---|---:|
| `provider` | `TEXT` | `ollama` | `select` | Yes |
| `model_name` | `TEXT` | `""` | `select` | Yes |

## `LLM_CHAT` (v1)

- Name: LLM Chat
- Category: `model`
- Description: Run a chat completion with a typed model handle and return plain text.

Inputs: `user_prompt` (`TEXT`), `system_prompt` (`TEXT`), `image` (`IMAGE`) - all optional.

Outputs: `response` (`TEXT`).

Controllers: `model` (`MODEL_HANDLE`, required, `scope: target`).

Parameters: `context_window`, `max_tokens`, `use_reasoning`.

## `LLM_STRUCTURED` (v1)

- Name: LLM Structured
- Category: `model`
- Description: Run structured generation and return schema-validated JSON.

Inputs: `user_prompt` (`TEXT`), `system_prompt` (`TEXT`), `image` (`IMAGE`) - all optional.

Outputs: `result` (`JSON`).

Controllers: `model` (`MODEL_HANDLE`, required, `scope: target`).

Parameters: `context_window`, `max_tokens`, `use_reasoning`, `response_schema`.

## `PROMPT` (v1)

- Name: Prompt
- Category: `input`
- Description: Provide generic prompt text to the workflow graph.

Outputs: `text` (`TEXT`).

Parameters: `prompt_text` (`TEXT`, required, textarea).

## `LOAD_DOCUMENTS` (v1)

- Name: Load Documents
- Category: `serialization`
- Description: Scan a folder and emit deferred `DOCUMENT_LIST` file references.

Outputs: `documents` (`DOCUMENT_LIST`).

Parameters:

| Name | Data Type | Default | UI Control | Required |
|---|---|---|---|---:|
| `folder_path` | `TEXT` | `""` | `directory` | Yes |
| `recursive` | `BOOLEAN` | `true` | `toggle` | No |

Behavior notes:
- Emits deferred records (`metadata.deferred_load = true`) to avoid eager file loading.
- Supports common text/document formats (`.txt`, `.md`, `.pdf`, `.doc`, `.docx`, `.json`, `.html`, `.csv`, `.xml`, `.yaml`, `.log`, etc.).

## `FIXED_SIZE_CHUNKS` (v1)

- Name: Fixed Size Chunks
- Category: `fragmentation`
- Description: Split documents or upstream chunks into fixed-size windows.

Inputs: `documents` (`DOCUMENT_LIST`) or `chunks` (`CHUNK_LIST`).

Outputs: `chunks` (`CHUNK_LIST`).

Parameters: `chunk_size`, `chunk_overlap`, `unit` (`words | characters`).

## `BY_DELIMITER_CHUNKS` (v1)

- Name: By Delimiter Chunks
- Category: `fragmentation`
- Description: Split by an explicit delimiter or preset and optionally keep delimiters.

Inputs: `documents` or `chunks`.

Outputs: `chunks`.

Parameters: `delimiter`, `keep_delimiter`, `drop_empty`, `max_chunk_size`, `overflow_strategy` (`split_further | discard | emit_as_is`).

## `BY_STRUCTURE_CHUNKS` (v1)

- Name: By Structure Chunks
- Category: `fragmentation`
- Description: Split by structural boundaries (paragraph/section/heading-content).

Inputs: `documents` or `chunks`.

Outputs: `chunks`.

Parameters: `strategy`, `max_chunk_size`, `chunk_overlap`, `unit`, `overflow_strategy`.

## `RECURSIVE_SPLIT_CHUNKS` (v1)

- Name: Recursive Split Chunks
- Category: `fragmentation`
- Description: Apply ordered separators from coarse to fine until chunk constraints are met.

Inputs: `documents` or `chunks`.

Outputs: `chunks`.

Parameters: `separators` (ordered string list), `chunk_size`, `chunk_overlap`, `unit`, `fallback_strategy` (`continue | force_split`).

## `SENTENCE_WINDOW_CHUNKS` (v1)

- Name: Sentence Window Chunks
- Category: `fragmentation`
- Description: Segment text into sentences and emit overlapping sentence windows.

Inputs: `documents` or `chunks`.

Outputs: `chunks`.

Parameters: `sentences_per_chunk`, `sentence_overlap`, `max_chunk_size`, `overflow_strategy`.

## `MERGE_SMALL_CHUNKS` (v1)

- Name: Merge Small Chunks
- Category: `fragmentation`
- Description: Merge consecutive fragments until target size thresholds are reached.

Inputs: `documents` or `chunks`.

Outputs: `chunks`.

Parameters: `target_chunk_size`, `unit`, `max_chunk_size`, `merge_strategy` (`sequential | greedy`), `preserve_boundaries`.

## `SAVE_TEXT` (v1)

- Name: Save Text
- Category: `serialization`
- Description: Save incoming `text`, `documents`, or `chunks` into one file or multiple files (Browse opens a Save As picker for filename selection).

Inputs: `text` (`TEXT`), `documents` (`DOCUMENT_LIST`), `chunks` (`CHUNK_LIST`) - optional; at least one non-empty input required at runtime.

Outputs: `artifact` (`JSON`).

Behavior notes:
- `output_path` is treated as a reference file path (name + optional extension).
- With `separate_files = true`, `output_path` is treated as a folder reference:
- If it includes an extension (for example `exports/chunks.txt`), the folder name uses the stem (`exports/chunks`).
- Outputs are written inside that folder as `folderName_00001`, `folderName_00002`, ... using the selected extension.
- Frontend Browse for `SAVE_TEXT.output_path` uses browser file/directory pickers only (no backend-native dialogs).
- In local browser runs, when Browse is used, selected file/directory handles are used client-side after execution so content is written to the user-selected local target.
- When this frontend-selected target is active, backend SAVE_TEXT skips writing to `resources/artifacts` for that node run.
- In local browser runs with `client_side_write`, backend SAVE_TEXT artifact also includes ordered `item_texts` so deferred `LOAD_DOCUMENTS` inputs can be written client-side without empty files.

Parameters:

| Name | Data Type | Default | UI Control | Required |
|---|---|---|---|---:|
| `output_path` | `TEXT` | `""` | `text` | Yes |
| `separate_files` | `BOOLEAN` | `false` | `toggle` | No |
| `extension` | `TEXT` | `.txt` | `select` | Yes |

Supported extensions: `.txt`, `.md`, `.doc`, `.pdf`.
## `LOAD_TEXT` (v1)

- Name: Load Text
- Category: `serialization`
- Description: Load plain text content from a local file path.

Outputs: `text` (`TEXT`).

Parameters: `storage_path` (`TEXT`, required).

## `SQL_DATABASE` (v1)

- Name: SQL Database
- Category: `control`
- Description: Configure a server SQL connection handle.

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `connection` | `DATABASE_CONNECTION` | No | `source` |

Parameters include server connection values (`db_engine`, `db_host`, `db_port`, `db_name`, `db_user`, `db_password`, `db_ssl`, `db_ssl_ca`, `db_connect_timeout`).

## `SQL_FILE_DATABASE` (v1)

- Name: Embedded SQL Database
- Category: `control`
- Description: Configure an embedded SQL file dataset (SQLite in v1) and expose a typed connection handle.

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `connection` | `DATABASE_CONNECTION` | No | `source` |

Parameters include `db_engine` (`sqlite`) and `db_path`, plus reserved compatibility fields.

## `TEXT_OUTPUT` (v1)

- Name: Text Output
- Category: `output`
- Description: Expose final text results.

Inputs: `text` (`TEXT`, required).

## `JSON_OUTPUT` (v1)

- Name: JSON Output
- Category: `output`
- Description: Expose final JSON results.

Inputs: `value` (`JSON`, required).
