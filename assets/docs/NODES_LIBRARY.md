# Nodes Library

This document defines the currently available workflow nodes, their contracts, and their expected behavior.

## Conventions

- **Versioning:** All nodes listed here are `v1`.
- **Input/Output notation:** `name (TYPE)` and `name (TYPE, required)` indicate port contracts.
- **Controller outputs:** Some nodes emit source/controller handles that must be wired into compatible downstream nodes.
- **Terminal nodes:** Output nodes publish final execution results and do not produce downstream values.

## Quick Index

| Category | Nodes |
| --- | --- |
| `control` | `ASSIGN_NAME` |
| `prompt` | `PROMPT`, `PROMPT_TEMPLATE` |
| `model` | `MODEL_PROVIDER`, `LLM_CHAT`, `LLM_STRUCTURED` |
| `embeddings` | `TEXT_EMBEDDING` |
| `serialization` | `LOAD_DOCUMENTS`, `LOAD_TEXT`, `SAVE_AS_FILE`, `SAVE_AS_FOLDER` |
| `text_segmentation` | `FIXED_SIZE_CHUNKS`, `BY_DELIMITER_CHUNKS`, `BY_STRUCTURE_CHUNKS`, `RECURSIVE_SPLIT_CHUNKS`, `REGEX_SPLIT_CHUNKS`, `SENTENCE_WINDOW_CHUNKS`, `MERGE_SMALL_CHUNKS` |
| `database` | `SQL_DATABASE`, `SQL_FILE_DATABASE` |
| `vector_storage` | `LANCE_DB` |
| `output` | `TEXT_OUTPUT`, `JSON_OUTPUT` |

## Control

### `ASSIGN_NAME` (`v1`)

- **Category:** `control`
- **Inputs:** `value (ANY, required)`
- **Output:** `variable (JSON)`
- **Behavior:** Emits a single-key JSON object in the form `{ "<name>": value }`, where `<name>` comes from the required node parameter.
- **Notes:** The upstream payload is preserved as-is and only wrapped into the named object.

## Prompt

### `PROMPT` (`v1`)

- **Category:** `prompt`
- **Inputs:** none
- **Output:** `text (TEXT)`
- **Behavior:** Emits `prompt_text` exactly as entered.
- **Notes:** No templating or transformation is applied.

### `PROMPT_TEMPLATE` (`v1`)

- **Category:** `prompt`
- **Inputs:** `variables (ANY, accepts_multiple)`
- **Output:** `text (TEXT)`
- **Behavior:** Renders templates using `{variable}` placeholders.
- **Validation rules:** Missing placeholders fail fast. Duplicate keys across incoming variable maps fail fast. Multiple incoming variable maps are merged into one dictionary before rendering.

## Model

### `MODEL_PROVIDER` (`v1`)

- **Category:** `model`
- **Inputs:** none
- **Output:** `model controller (MODEL_HANDLE, source)`
- **Behavior:** Publishes provider/model configuration for downstream model nodes.
- **Notes:** Includes configurable request timeout in seconds (default: `120`).

### `LLM_CHAT` (`v1`)

- **Category:** `model`
- **Inputs:** `user_prompt (TEXT)`, `system_prompt (TEXT)`, `image (IMAGE)`
- **Output:** `response (TEXT)`
- **Behavior:** Executes chat-style inference and returns text.
- **Requirements:** Must receive a compatible `model` controller from `MODEL_PROVIDER`.

### `LLM_STRUCTURED` (`v1`)

- **Category:** `model`
- **Inputs:** `user_prompt (TEXT)`, `system_prompt (TEXT)`, `image (IMAGE)`
- **Output:** `result (JSON)`
- **Behavior:** Executes structured inference and returns JSON.
- **Requirements:** Must receive a compatible `model` controller from `MODEL_PROVIDER`.
- **Validation:** Model output is validated against `response_schema`.

## Serialization

### `LOAD_DOCUMENTS` (`v1`)

- **Category:** `serialization`
- **Inputs:** none
- **Output:** `documents (DOCUMENT_LIST)`
- **Behavior:** Produces deferred document records from a selected folder.
- **Notes:** Document content resolution can happen downstream when needed.

### `LOAD_TEXT` (`v1`)

- **Category:** `serialization`
- **Inputs:** none
- **Output:** `text (TEXT)`
- **Behavior:** Loads text from a selected local file path.

### `SAVE_AS_FILE` (`v1`)

- **Category:** `serialization`
- **Inputs:** `text (TEXT)`, `documents (DOCUMENT_LIST)`, `chunks (CHUNK_LIST)`
- **Output:** `artifact (JSON)`
- **Behavior:** Writes one file.
- **Notes:** Multi-item input is concatenated in indexed order with a double-newline separator. Supports deferred document resolution. Supports client-side write mode metadata.

### `SAVE_AS_FOLDER` (`v1`)

- **Category:** `serialization`
- **Inputs:** `text (TEXT)`, `documents (DOCUMENT_LIST)`, `chunks (CHUNK_LIST)`
- **Output:** `artifact (JSON)`
- **Behavior:** Writes one file per item with indexed filenames.
- **Notes:** Supports deferred document resolution. Supports client-side write mode metadata.

## Text Segmentation

All segmentation nodes share the same port contract:

- **Inputs:** `text (TEXT)`, `documents (DOCUMENT_LIST)`, `chunks (CHUNK_LIST)`
- **Output:** `chunks (CHUNK_LIST)`

### `FIXED_SIZE_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Splits input into fixed-size chunks using configured unit and overlap.

### `BY_DELIMITER_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Splits by delimiter or preset separator sets, with overflow handling options.

### `BY_STRUCTURE_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Splits on structural boundaries (for example paragraph, section, and heading/content boundaries).

### `RECURSIVE_SPLIT_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Applies an ordered separator list recursively with fallback strategy.

### `REGEX_SPLIT_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Splits text using a regex pattern.

### `SENTENCE_WINDOW_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Builds overlapping windows of sentence-based chunks.

### `MERGE_SMALL_CHUNKS` (`v1`)

- **Category:** `text_segmentation`
- **Behavior:** Merges small adjacent chunks toward configured target-size constraints.

## Embeddings

### `TEXT_EMBEDDING` (`v1`)

- **Category:** `embeddings`
- **Inputs:** `text (TEXT)`, `documents (DOCUMENT_LIST)`, `chunks (CHUNK_LIST)`
- **Output:** `points (VECTOR_POINT_LIST)`
- **Behavior:** Applies text embeddings and returns vector points with preserved text and source metadata.
- **Notes:** Provider/model selection is built into the node. Supported providers are `cloud`, `huggingface`, and `ollama`.

## Database

### `SQL_DATABASE` (`v1`)

- **Category:** `database`
- **Inputs:** none
- **Output:** `connection controller (DATABASE_CONNECTION, source)`
- **Behavior:** Exposes an external database connection handle for SQL execution nodes.

### `SQL_FILE_DATABASE` (`v1`)

- **Category:** `database`
- **Inputs:** none
- **Output:** `connection controller (DATABASE_CONNECTION, source)`
- **Behavior:** Exposes an embedded/SQLite database connection handle.

## Vector Storage

### `LANCE_DB` (`v1`)

- **Category:** `vector_storage`
- **Inputs:** `points (VECTOR_POINT_LIST, accepts_multiple)`
- **Output:** `store (VECTOR_STORE_HANDLE)`
- **Behavior:** Stores embeddings in a LanceDB table located under the configured storage path.
- **Notes:** Supports `overwrite` and `append` write modes plus metric and vector-index configuration.

## Output

### `TEXT_OUTPUT` (`v1`)

- **Category:** `output`
- **Inputs:** `text (TEXT, required)`
- **Output:** none (terminal node)
- **Behavior:** Publishes final text results in execution outputs.

### `JSON_OUTPUT` (`v1`)

- **Category:** `output`
- **Inputs:** `value (JSON, required)`
- **Output:** none (terminal node)
- **Behavior:** Publishes final JSON results in execution outputs.
