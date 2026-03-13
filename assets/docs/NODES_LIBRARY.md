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
- `processing`
- `fragmentation`
- `output`
- `serialization`
- `control`

## Node Index

| Node ID | Version | Name | Category | Manifest |
|---|---:|---|---|---|
| `LLM_CHAT` | 1 | LLM Chat | model | `llm_chat_v1.json` |
| `LLM_STRUCTURED` | 1 | LLM Structured | model | `llm_structured_v1.json` |
| `MODEL_PROVIDER` | 1 | Model Provider | model | `model_provider_v1.json` |
| `PROMPT` | 1 | Prompt | input | `prompt_v1.json` |
| `WEB_SCRAPER` | 1 | Web Scraper | input | `web_scraper_v1.json` |
| `LOAD_DOCUMENTS` | 1 | Load Documents | serialization | `load_documents_v1.json` |
| `FIXED_SIZE_CHUNKS` | 1 | Fixed Size Chunks | fragmentation | `fixed_size_chunks_v1.json` |
| `SQL_DATABASE` | 1 | SQL Database | control | `sql_database_v1.json` |
| `SQL_FILE_DATABASE` | 1 | SQL File Database | control | `sql_file_database_v1.json` |
| `TEXT_OUTPUT` | 1 | Text Output | output | `text_output_v1.json` |
| `JSON_OUTPUT` | 1 | JSON Output | output | `json_output_v1.json` |

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
| `response_schema` | `JSON` | `{"type":"object","properties":{},"required":[]}` | `json` | Yes | JSON Schema used to validate the structured response. Example: `{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}`. |

## `PROMPT` (v1)

- Name: Prompt
- Category: `input`
- Description: Provide generic prompt text to the workflow graph.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `prompt_text` | `TEXT` | `""` | `textarea` | Yes | Prompt text emitted to downstream nodes. |

## `WEB_SCRAPER` (v1)

- Name: Web Scraper
- Category: `input`
- Description: Fetch an HTML page and convert it into normalized document text for downstream processing.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `documents` | `DOCUMENT_LIST` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `url` | `TEXT` | `""` | `text` | Yes | HTTP or HTTPS URL to fetch. |
| `timeout_s` | `JSON` | `15` | `number` | No | Request timeout in seconds. |
| `strip_html_content` | `BOOLEAN` | `true` | `toggle` | No | Convert fetched content to plain text before emitting it. |

## `LOAD_DOCUMENTS` (v1)

- Name: Load Documents
- Category: `serialization`
- Description: Scan a selected folder and emit a deferred `DOCUMENT_LIST` payload containing document file-path references.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `documents` | `DOCUMENT_LIST` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `folder_path` | `TEXT` | `""` | `directory` | Yes | Staged server folder path produced from the frontend folder picker upload flow. |
| `recursive` | `BOOLEAN` | `true` | `toggle` | No | Include files from subdirectories when enabled. |

Behavior notes:
- Supported extensions include `.txt`, `.pdf`, `.doc`, `.docx`, `.md`, plus common text formats (`.html`, `.json`, `.csv`, `.xml`, `.yaml`, `.log`, etc.).
- The node does **not** load file contents into memory when scanning an existing server directory path.
- It emits documents with deferred metadata (`metadata.deferred_load = true`) so downstream processing nodes can load content only when needed.
- In the workflow UI, the Browse action uses a frontend folder picker and stages selected files into `ParaGraph/resources/artifacts/browser_uploads`; `folder_path` is set to that staged directory.

## `FIXED_SIZE_CHUNKS` (v1)

- Name: Fixed Size Chunks
- Category: `fragmentation`
- Description: Split incoming documents or upstream chunks into fixed-size chunks for chained fragmentation pipelines.

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `documents` | `DOCUMENT_LIST` | No |
| `chunks` | `CHUNK_LIST` | No |

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `chunks` | `CHUNK_LIST` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `chunk_size` | `JSON` | `800` | `number` | Yes | Maximum chunk length measured in the selected unit. |
| `chunk_overlap` | `JSON` | `80` | `number` | Yes | Overlap between consecutive chunks in the selected unit. |
| `unit` | `TEXT` | `words` | `select` | Yes | Chunking unit. Supported values: `words`, `characters`. |

Behavior notes:
- Supports chained fragmentation by accepting `CHUNK_LIST` from upstream fragmentation nodes.
- Deferred document records are hydrated one-by-one during fragmentation.
- At least one non-empty input (`documents` or `chunks`) is required at runtime.
## `SQL_DATABASE` (v1)

- Name: SQL Database
- Category: `control`
- Description: Configure a server SQL database connection and expose a reusable typed controller handle.
- UI behavior: Includes a node-level **Check Connection** button that validates connectivity and reports success/failure.

Inputs: None.

Outputs: None.

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `connection` | `DATABASE_CONNECTION` | No | `source` |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `db_engine` | `TEXT` | `postgres` | `select` | Yes | Engine for server-based SQL connections. Supported values: `postgres`, `mysql`. |
| `db_host` | `TEXT` | `127.0.0.1` | `text` | Yes | Database host or IP address. |
| `db_port` | `JSON` | `5432` | `number` | Yes | Database port. |
| `db_name` | `TEXT` | `""` | `text` | Yes | Database name. |
| `db_user` | `TEXT` | `postgres` | `text` | Yes | Database username. |
| `db_password` | `TEXT` | `change_me` | `password` | No | Database password. |
| `db_ssl` | `BOOLEAN` | `false` | `toggle` | No | Enable SSL/TLS for server-based SQL connections. |
| `db_ssl_ca` | `TEXT` | `""` | `file` | No | Optional CA certificate path when SSL is enabled. |
| `db_connect_timeout` | `JSON` | `30` | `number` | No | Connection timeout in seconds. |

## `SQL_FILE_DATABASE` (v1)

- Name: SQL File Database
- Category: `control`
- Description: Configure a file-based SQL dataset (SQLite for v1) and expose a reusable typed controller handle.
- UI behavior: Includes a node-level **Check Connection** button that validates connectivity and reports success/failure.

Inputs: None.

Outputs: None.

Controllers:

| Name | Data Type | Required | Scope |
|---|---|---:|---|
| `connection` | `DATABASE_CONNECTION` | No | `source` |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `db_engine` | `TEXT` | `sqlite` | `select` | Yes | File database engine. Currently only `sqlite`. |
| `db_path` | `TEXT` | `""` | `file` | Yes | Path to the database file selected from the local file picker. |
| `db_port` | `JSON` | `5432` | `number` | No | Reserved for future engine compatibility. |
| `db_name` | `TEXT` | `FAIRS` | `text` | No | Logical dataset name. |
| `db_user` | `TEXT` | `postgres` | `text` | No | Reserved for future engine compatibility. |
| `db_password` | `TEXT` | `change_me` | `password` | No | Reserved for future engine compatibility. |
| `db_ssl` | `BOOLEAN` | `false` | `toggle` | No | Reserved for future engine compatibility. |
| `db_ssl_ca` | `TEXT` | `""` | `file` | No | Reserved for future engine compatibility. |
| `db_connect_timeout` | `JSON` | `30` | `number` | No | Connection timeout in seconds. |

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

## `JSON_OUTPUT` (v1)

- Name: JSON Output
- Category: `output`
- Description: Expose final JSON results.
- UI behavior: JSON widget boxes include a **Validate** button that marks valid/invalid JSON with neon border feedback (and pretty-prints valid JSON).

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `value` | `JSON` | Yes |

Outputs: None.

Parameters: None.
