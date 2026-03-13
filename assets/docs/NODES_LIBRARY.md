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
| `TEXT_OUTPUT` | 1 | Text Output | output | `text_output_v1.json` |
| `JSON_OUTPUT` | 1 | JSON Output | output | `json_output_v1.json` |
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

Inputs:

| Name | Data Type | Required |
|---|---|---:|
| `value` | `JSON` | Yes |

Outputs: None.

Parameters: None.
