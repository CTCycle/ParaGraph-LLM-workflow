# Nodes Library
Last updated: 2026-04-15

Source of truth for shipped nodes: `ParaGraph/resources/nodes/*.json`.

## 1. Current Node Inventory

| Category | Node IDs |
| --- | --- |
| `web` | `API_CALL`, `FETCH_HTML` |
| `prompt` | `PROMPT`, `PROMPT_TEMPLATE` |
| `model` | `MODEL_PROVIDER`, `LLM_CHAT`, `LLM_STRUCTURED` |
| `memory` | `CHAT_HISTORY_MEMORY`, `CHAT_HISTORY_PERSISTED` |
| `embeddings` | `TEXT_EMBEDDING` |
| `retrieval` | `SIMILARITY_SEARCH`, `RERANK_RESULTS` |
| `serialization` | `LOAD_DOCUMENTS`, `LOAD_TEXT`, `SAVE_AS_FILE`, `SAVE_AS_FOLDER` |
| `text_segmentation` | `FIXED_SIZE_CHUNKS`, `BY_DELIMITER_CHUNKS`, `BY_STRUCTURE_CHUNKS`, `RECURSIVE_SPLIT_CHUNKS`, `REGEX_SPLIT_CHUNKS`, `SENTENCE_WINDOW_CHUNKS`, `MERGE_SMALL_CHUNKS` |
| `database` | `SQL_DATABASE`, `SQL_FILE_DATABASE` |
| `vector_storage` | `VECTOR_STORE` |
| `output` | `TEXT_OUTPUT`, `JSON_OUTPUT` |

## 2. Node Summary

- `PROMPT`: emits fixed text.
- `PROMPT_TEMPLATE`: renders prompt text from template placeholders + variables.
- `MODEL_PROVIDER`: emits typed model handle for generation nodes.
- `LLM_CHAT`: text generation node.
- `LLM_STRUCTURED`: structured generation node with JSON-schema validation after generation.
- `CHAT_HISTORY_MEMORY`: emits `CHAT_HISTORY_HANDLE` backed by in-memory storage.
- `CHAT_HISTORY_PERSISTED`: emits `CHAT_HISTORY_HANDLE` backed by `file` or `database` storage.
- `TEXT_EMBEDDING`: creates vectors from text/documents/chunks.
- `VECTOR_STORE`: persists vectors to selected backend.
- `SIMILARITY_SEARCH`: retrieves scored hits from vector store.
- `RERANK_RESULTS`: deterministic reranking over `RETRIEVAL_RESULTS`.
- `LOAD_DOCUMENTS` / `LOAD_TEXT`: local ingestion nodes.
- `SAVE_AS_FILE` / `SAVE_AS_FOLDER`: artifact serialization nodes.
- Chunking nodes: segmentation utilities for RAG ingestion.

## 3. Core Contracts

- Manifest-driven validation covers ports, controllers, parameters, and runtime metadata.
- Data links and controller links are distinct and type-checked.
- `accepts_multiple` inputs/controllers are aggregated at runtime.
- Output nodes publish terminal outputs.

## 4. Embedding And Provider Matrix

`TEXT_EMBEDDING` providers are explicit:
- `openai`
- `gemini`
- `huggingface`
- `ollama`

`cloud` bucket is not used.

Model options are provider-catalog driven via `/providers/models` and filtered by `supports_embeddings=true`.

Claude must never be used for embeddings.

## 5. Vector Store Provider Matrix

`VECTOR_STORE` provider options:
- `lancedb`
- `qdrant`
- `pinecone`
- `weaviate`
- `milvus`
- `chroma`
- `faiss`

Critical parameter rules:
- Local providers (`lancedb`, `chroma`, `faiss`) require `storage_path`.
- Remote providers (`qdrant`, `pinecone`, `weaviate`, `milvus`) require `endpoint_url`.

## 6. Retrieval And RAG Chain

Recommended RAG flow:
1. `LOAD_DOCUMENTS`
2. Chunking node(s)
3. `TEXT_EMBEDDING`
4. `VECTOR_STORE`
5. `PROMPT_TEMPLATE` (query construction)
6. `SIMILARITY_SEARCH`
7. `RERANK_RESULTS`
8. `PROMPT_TEMPLATE` (answer synthesis)
9. `LLM_CHAT` or `LLM_STRUCTURED`

Important:
- Query construction is handled by `PROMPT_TEMPLATE`.
- No dedicated query-prompt node is required or shipped.

## 7. `RERANK_RESULTS` Contract

- Node ID: `RERANK_RESULTS`
- Input: `results` (`RETRIEVAL_RESULTS`, required), `query` (`TEXT`, optional)
- Output: `results` (`RETRIEVAL_RESULTS`)
- Runtime key: `rerank_results`
- Deterministic local scoring strategies:
  - `original_score`
  - `term_overlap`
  - `exact_phrase`
  - `metadata_match`
  - `weighted_composite`

## 8. Compatibility Constraints

- Hugging Face image input is explicitly rejected in current local generation runtime path.
- Hugging Face structured output remains best-effort generation + JSON validation.
- Hugging Face metadata indicates no streaming/tool-calling support.
- Claude embeddings are unsupported by provider capabilities.

## 8.1 Chat History Contract

- `LLM_CHAT` and `LLM_STRUCTURED` accept optional `history` controller input of type `CHAT_HISTORY_HANDLE`.
- History node parameters:
  - `max_messages` (minimum `1`)
  - `separator`
  - `keep_prompt_type`
  - persisted node only: `storage_backend` (`file` or `database`)
- Persisted file storage path:
  - `ParaGraph/resources/chat_history/<workflow_id>/<execution_session_id>/<node_id>.json`
- Persisted database storage:
  - one row per message in `chat_history_messages` with workflow/session/node identifiers, role, content, and timestamp.

## 11. `SIMILARITY_SEARCH` Contract Matrix

- Node ID: `SIMILARITY_SEARCH`
- Input: `query` (`TEXT`, required)
- Output: `results` (`RETRIEVAL_RESULTS`)
- Required controllers:
  - `embedding` (`JSON`, target)
  - `store` (`VECTOR_STORE_HANDLE`, target)
- Runtime key: `similarity_search`

Parameter matrix:
- `search_mode`
  - options: `vector`, `hybrid`
  - default: `vector`
- `search_engine`
  - options: `native`, `faiss_augmented`
  - default: `native`
  - `native` is the default and preferred mode
  - `faiss_augmented` is optional and backend-dependent
- `similarity_strategy`
  - options: `cosine`, `euclidean`, `dot`
  - default: `cosine`

Execution constraints:
- Native vector store indexing/query must be used by default.
- Metric must remain compatible with connected `VECTOR_STORE.distance_metric`.
- Unsupported mode/backend combinations must be rejected before execution.

## 9. Workflow Templates

Workflow templates are manifest-driven and loaded from:
- `ParaGraph/resources/workflow_templates/*.json`

Templates are validated at load time against:
- typed template schema
- node catalog manifest availability (`required_nodes`)
- compiler validity (`definition` + `visual_graph`)

Shipped templates:
- `system_user_llm_structured_output_v1`
- `system_user_llm_chat_output_v1`
- `load_documents_chunk_embed_store_v1`

## 10. Node Catalog Scope For This Release

- No new node IDs were introduced.
- Existing node contracts and execution handlers remain the source of truth.
