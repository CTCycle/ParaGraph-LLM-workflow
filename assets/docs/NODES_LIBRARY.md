# Nodes Library

This document is the reference for all currently implemented workflow nodes and their parameters.

Source of truth: `ParaGraph/resources/nodes/*.json`

## Node Index

| Node ID | Version | Name | Category | Manifest |
|---|---:|---|---|---|
| `CLOUD_LLM_CHAT` | 1 | Cloud LLM Chat | model | `cloud_llm_chat_v1.json` |
| `CLOUD_STRUCTURED_RESPONSE` | 1 | Cloud Structured Response | model | `cloud_structured_response_v1.json` |
| `EMBEDDING_MODEL` | 1 | Embedding Model | model | `embedding_model_v1.json` |
| `HUGGINGFACE_LLM_CHAT` | 1 | HuggingFace LLM Chat | model | `huggingface_llm_chat_v1.json` |
| `HUGGINGFACE_STRUCTURED_RESPONSE` | 1 | HuggingFace Structured Response | model | `huggingface_structured_response_v1.json` |
| `IF` | 1 | If | control | `if_v1.json` |
| `IMAGE_INPUT` | 1 | Image Input | input | `image_input_v1.json` |
| `IMAGE_OUTPUT` | 1 | Image Output | output | `image_output_v1.json` |
| `LOAD_TEXT` | 1 | Load Text | serialization | `load_text_v1.json` |
| `OLLAMA_LLM_CHAT` | 1 | Ollama LLM Chat | model | `ollama_llm_chat_v1.json` |
| `OLLAMA_STRUCTURED_RESPONSE` | 1 | Ollama Structured Response | model | `ollama_structured_response_v1.json` |
| `ROUTER` | 1 | Router | control | `router_v1.json` |
| `SAVE_TEXT` | 1 | Save Text | serialization | `save_text_v1.json` |
| `SYSTEM_PROMPT` | 1 | System Prompt | input | `system_prompt_v1.json` |
| `TEMPLATE_FORMAT` | 1 | Template Format | processing | `template_format_v1.json` |
| `TEXT_OUTPUT` | 1 | Text Output | output | `text_output_v1.json` |
| `TEXT_SPLIT` | 1 | Text Split | processing | `text_split_v1.json` |
| `TOKENIZE` | 1 | Tokenize | processing | `tokenize_v1.json` |
| `USER_PROMPT` | 1 | User Prompt | input | `user_prompt_v1.json` |

---

## `CLOUD_LLM_CHAT` (v1)

- Name: Cloud LLM Chat
- Category: `model`
- Description: Chat with an OpenAI, Gemini, or Claude model and return plain text.

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

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `provider` | `TEXT` | `openai` | `select` | Yes | Cloud provider selection. |
| `model_name` | `TEXT` | `""` | `select` | Yes | Provider model identifier. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable provider-specific reasoning behavior when available. |

## `CLOUD_STRUCTURED_RESPONSE` (v1)

- Name: Cloud Structured Response
- Category: `model`
- Description: Generate typed JSON responses with an OpenAI, Gemini, or Claude model.

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

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `provider` | `TEXT` | `openai` | `select` | Yes | Cloud provider selection. |
| `model_name` | `TEXT` | `""` | `select` | Yes | Provider model identifier. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable provider-specific reasoning behavior when available. |
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

## `HUGGINGFACE_LLM_CHAT` (v1)

- Name: HuggingFace LLM Chat
- Category: `model`
- Description: Chat with a locally served HuggingFace model and return plain text.

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

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `model_name` | `TEXT` | `""` | `select` | Yes | HuggingFace model identifier. |
| `context_window` | `JSON` | `0` | `number` | No | Context window size. Use `0` for provider-managed context. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable reasoning-oriented execution when the model supports it. |

## `HUGGINGFACE_STRUCTURED_RESPONSE` (v1)

- Name: HuggingFace Structured Response
- Category: `model`
- Description: Generate typed JSON responses with a locally served HuggingFace model.

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

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `model_name` | `TEXT` | `""` | `select` | Yes | HuggingFace model identifier. |
| `context_window` | `JSON` | `0` | `number` | No | Context window size. Use `0` for provider-managed context. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable reasoning-oriented execution when the model supports it. |
| `response_schema` | `JSON` | `{"type":"object","properties":{},"required":[]}` | `json` | Yes | JSON Schema used to validate the structured response. |

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
- Description: Load text content from the artifacts directory.

Inputs: None.

Outputs:

| Name | Data Type | Required |
|---|---|---:|
| `text` | `TEXT` | Yes |

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `storage_path` | `TEXT` | `saved_text.txt` | `text` | No | Relative path inside ParaGraph/resources/artifacts. |

## `OLLAMA_LLM_CHAT` (v1)

- Name: Ollama LLM Chat
- Category: `model`
- Description: Chat with an Ollama-served language model and return plain text.

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

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `model_name` | `TEXT` | `""` | `select` | Yes | Ollama model identifier. |
| `context_window` | `JSON` | `0` | `number` | No | Context window size. Use `0` for provider-managed context. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable reasoning-oriented execution when the model supports it. |

## `OLLAMA_STRUCTURED_RESPONSE` (v1)

- Name: Ollama Structured Response
- Category: `model`
- Description: Generate typed JSON responses with an Ollama-served model.

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

Parameters:

| Name | Data Type | Default | UI Control | Required | Description |
|---|---|---|---|---:|---|
| `model_name` | `TEXT` | `""` | `select` | Yes | Ollama model identifier. |
| `context_window` | `JSON` | `0` | `number` | No | Context window size. Use `0` for provider-managed context. |
| `max_tokens` | `JSON` | `512` | `number` | No | Maximum output token count. |
| `use_reasoning` | `BOOLEAN` | `false` | `toggle` | No | Enable reasoning-oriented execution when the model supports it. |
| `response_schema` | `JSON` | `{"type":"object","properties":{},"required":[]}` | `json` | Yes | JSON Schema used to validate the structured response. |

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
- Description: Persist text content to the artifacts directory.

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
| `storage_path` | `TEXT` | `saved_text.txt` | `text` | No | Relative path inside ParaGraph/resources/artifacts. |

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
