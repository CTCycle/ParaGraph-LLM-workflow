# Nodes Library

This document tracks the current workflow node catalog.

Source of truth: `ParaGraph/resources/nodes/*.json`

## Connection Types

Node manifests support three connection collections:

- `inputs`: data dependencies consumed by node execution.
- `outputs`: data payloads produced by node execution.
- `controllers`: behavior/configuration links (not regular data flow), with directional placement metadata (`scope`).

Controller placement contract:
- `scope: source` -> right edge (same lane as outputs).
- `scope: target` -> left edge (same lane as inputs).
- `scope: both` -> both source and target handles.

## Categories

Current category set:

- `input`
- `prompt`
- `model`
- `processing`
- `text_segmentation`
- `output`
- `serialization`
- `database`
- `control`

`fragmentation` is not part of the catalog anymore.

## Node Index

| Node ID | Version | Name | Category | Manifest |
|---|---:|---|---|---|
| `BY_DELIMITER_CHUNKS` | 1 | By Delimiter Chunks | `text_segmentation` | `by_delimiter_chunks_v1.json` |
| `BY_STRUCTURE_CHUNKS` | 1 | By Structure Chunks | `text_segmentation` | `by_structure_chunks_v1.json` |
| `FIXED_SIZE_CHUNKS` | 1 | Fixed Size Chunks | `text_segmentation` | `fixed_size_chunks_v1.json` |
| `JSON_OUTPUT` | 1 | JSON Output | `output` | `json_output_v1.json` |
| `LLM_CHAT` | 1 | LLM Chat | `model` | `llm_chat_v1.json` |
| `LLM_STRUCTURED` | 1 | LLM Structured | `model` | `llm_structured_v1.json` |
| `LOAD_DOCUMENTS` | 1 | Load Documents | `serialization` | `load_documents_v1.json` |
| `LOAD_TEXT` | 1 | Load Text | `serialization` | `load_text_v1.json` |
| `MERGE_SMALL_CHUNKS` | 1 | Merge Small Chunks | `text_segmentation` | `merge_small_chunks_v1.json` |
| `MODEL_PROVIDER` | 1 | Model Provider | `model` | `model_provider_v1.json` |
| `PROMPT` | 1 | Prompt | `prompt` | `prompt_v1.json` |
| `PROMPT_TEMPLATE` | 1 | Prompt Template | `prompt` | `prompt_template_v1.json` |
| `RECURSIVE_SPLIT_CHUNKS` | 1 | Recursive Split Chunks | `text_segmentation` | `recursive_split_chunks_v1.json` |
| `REGEX_SPLIT_CHUNKS` | 1 | Regex Split Chunks | `text_segmentation` | `regex_split_chunks_v1.json` |
| `SAVE_AS_FILE` | 1 | Save As File | `serialization` | `save_as_file_v1.json` |
| `SAVE_AS_FOLDER` | 1 | Save As Folder | `serialization` | `save_as_folder_v1.json` |
| `SENTENCE_WINDOW_CHUNKS` | 1 | Sentence Window Chunks | `text_segmentation` | `sentence_window_chunks_v1.json` |
| `SQL_DATABASE` | 1 | SQL Database | `database` | `sql_database_v1.json` |
| `SQL_FILE_DATABASE` | 1 | Embedded SQL Database | `database` | `sql_file_database_v1.json` |
| `TEXT_OUTPUT` | 1 | Text Output | `output` | `text_output_v1.json` |

---

## `PROMPT` (v1)

- Category: `prompt`
- Output: `text` (`TEXT`)
- Parameter: `prompt_text` (`TEXT`, textarea)

## `PROMPT_TEMPLATE` (v1)

- Category: `prompt`
- Description: Compose prompt text from a template with up to 8 optional values.

Inputs:
- `var_1`..`var_8` (`ANY`, optional)

Outputs:
- `text` (`TEXT`)

Parameters:
- `template` (`TEXT`, required, textarea)
- `variable_names` (`JSON`, string-list, max 8)
- `missing_variable` (`TEXT`, select: `error | empty | keep_placeholder`)
- `cleanup` (`TEXT`, select: `none | trim_lines | drop_empty_lines | collapse_blank_lines`)

Behavior:
- Placeholders use `{{name}}` syntax.
- `variable_names[i]` aliases `var_(i+1)`.
- Missing placeholder behavior is controlled by `missing_variable`.
- Non-text inputs are coerced to text; list-like document/chunk values are joined by blank lines.

## `MODEL_PROVIDER` (v1)

- Category: `model`
- Controller output: `model` (`MODEL_HANDLE`, `scope: source`)
- Parameters: `provider`, `model_name`

## `LLM_CHAT` (v1)

- Category: `model`
- Inputs: `user_prompt` (`TEXT`), `system_prompt` (`TEXT`), `image` (`IMAGE`)
- Controller input: `model` (`MODEL_HANDLE`, required, `scope: target`)
- Output: `response` (`TEXT`)

## `LLM_STRUCTURED` (v1)

- Category: `model`
- Inputs: `user_prompt` (`TEXT`), `system_prompt` (`TEXT`), `image` (`IMAGE`)
- Controller input: `model` (`MODEL_HANDLE`, required, `scope: target`)
- Output: `result` (`JSON`)
- Parameters include `response_schema`

## `LOAD_DOCUMENTS` (v1)

- Category: `serialization`
- Output: `documents` (`DOCUMENT_LIST`)
- Parameters: `folder_path`, `recursive`
- Emits deferred records (`metadata.deferred_load = true`) for scalable processing.

## `LOAD_TEXT` (v1)

- Category: `serialization`
- Output: `text` (`TEXT`)
- Parameter: `storage_path`
- Uses shared ingestion loader for text/document/pdf handling with encoding fallback.

## Text Segmentation Nodes (v1)

Category for all nodes below: `text_segmentation`

- `FIXED_SIZE_CHUNKS`: fixed-size windows by `words|characters`.
- `BY_DELIMITER_CHUNKS`: split by delimiter/preset with overflow strategy.
- `BY_STRUCTURE_CHUNKS`: split by paragraph/section/heading-content.
- `RECURSIVE_SPLIT_CHUNKS`: ordered separators with fallback strategy.
- `REGEX_SPLIT_CHUNKS`: regex-driven split using Python `re`.
- `SENTENCE_WINDOW_CHUNKS`: overlapping sentence windows.
- `MERGE_SMALL_CHUNKS`: merge adjacent chunks to target size.

## `SAVE_AS_FILE` (v1)

- Category: `serialization`
- Inputs: `text`, `documents`, `chunks` (at least one non-empty at runtime)
- Output: `artifact` (`JSON`)
- Writes a single file; multi-item input is concatenated with `/n/n`.
- Supports deferred document resolution and client-side write mode metadata.

## `SAVE_AS_FOLDER` (v1)

- Category: `serialization`
- Inputs: `text`, `documents`, `chunks` (at least one non-empty at runtime)
- Output: `artifact` (`JSON`)
- Writes one file per item with indexed filenames.
- Supports deferred document resolution and client-side write mode metadata.

## `SQL_DATABASE` (v1)

- Category: `database`
- Controller output: `connection` (`DATABASE_CONNECTION`, `scope: source`)
- Parameters include server DB connectivity settings.

## `SQL_FILE_DATABASE` (v1)

- Category: `database`
- Controller output: `connection` (`DATABASE_CONNECTION`, `scope: source`)
- Parameters include `db_engine=sqlite` and `db_path`.

## Outputs

- `TEXT_OUTPUT` (v1): category `output`, input `text` (`TEXT`) -> output `text`.
- `JSON_OUTPUT` (v1): category `output`, input `value` (`JSON`) -> output `json`.
