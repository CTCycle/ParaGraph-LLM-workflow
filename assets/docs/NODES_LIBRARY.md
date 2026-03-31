# Nodes Library

Source of truth for available workflow nodes is the manifest set in:

- `ParaGraph/resources/nodes/*.json`

All currently shipped manifests are version `v1`.

## 1. Current Node Inventory

| Category | Node IDs |
| --- | --- |
| `input` | |
| `web` | `API_CALL`, `FETCH_HTML` |
| `control` | `ASSIGN_NAME` |
| `prompt` | `PROMPT`, `PROMPT_TEMPLATE` |
| `model` | `MODEL_PROVIDER`, `LLM_CHAT`, `LLM_STRUCTURED` |
| `embeddings` | `TEXT_EMBEDDING` |
| `retrieval` | `SIMILARITY_SEARCH` |
| `serialization` | `LOAD_DOCUMENTS`, `LOAD_TEXT`, `SAVE_AS_FILE`, `SAVE_AS_FOLDER` |
| `text_segmentation` | `FIXED_SIZE_CHUNKS`, `BY_DELIMITER_CHUNKS`, `BY_STRUCTURE_CHUNKS`, `RECURSIVE_SPLIT_CHUNKS`, `REGEX_SPLIT_CHUNKS`, `SENTENCE_WINDOW_CHUNKS`, `MERGE_SMALL_CHUNKS` |
| `database` | `SQL_DATABASE`, `SQL_FILE_DATABASE` |
| `vector_storage` | `LANCE_DB` |
| `output` | `TEXT_OUTPUT`, `JSON_OUTPUT` |

## 2. Node Summary

- `ASSIGN_NAME`: wraps an upstream value into a named JSON map.
- `API_CALL`: calls a REST JSON/text endpoint (GET/POST) and emits text/json plus normalized response metadata.
- `FETCH_HTML`: fetches webpage HTML and emits raw html, cleaned text, and response metadata.
- `PROMPT`: emits fixed prompt text.
- `PROMPT_TEMPLATE`: renders prompt text from template + variables.
- `MODEL_PROVIDER`: emits a typed model-controller handle.
- `LLM_CHAT`: runs chat completion using model handle + prompt input.
- `LLM_STRUCTURED`: runs structured generation using model handle + prompt input.
- `TEXT_EMBEDDING`: produces dense embedding vectors from text/doc/chunk inputs.
- `SIMILARITY_SEARCH`: embeds query text and retrieves top-k nearest vectors from a connected vector store.
- `LOAD_DOCUMENTS`: scans a folder and emits document records.
- `LOAD_TEXT`: reads text from a local file path.
- `SAVE_AS_FILE`: serializes text/docs/chunks into one output file.
- `SAVE_AS_FOLDER`: serializes text/docs/chunks into output folder files.
- `FIXED_SIZE_CHUNKS`: fixed-size segmentation.
- `BY_DELIMITER_CHUNKS`: delimiter-based segmentation.
- `BY_STRUCTURE_CHUNKS`: structure-aware segmentation (paragraph/heading boundaries).
- `RECURSIVE_SPLIT_CHUNKS`: recursive separator fallback segmentation.
- `REGEX_SPLIT_CHUNKS`: regex-based segmentation.
- `SENTENCE_WINDOW_CHUNKS`: sentence-window segmentation with overlap.
- `MERGE_SMALL_CHUNKS`: merges small adjacent fragments.
- `SQL_DATABASE`: creates SQL DB controller handle from connection parameters.
- `SQL_FILE_DATABASE`: creates embedded SQL DB controller handle.
- `LANCE_DB`: stores embedding vectors in a local LanceDB table.
- `TEXT_OUTPUT`: terminal text output node.
- `JSON_OUTPUT`: terminal JSON output node.

## 3. Core Contract Rules

- Node contract validation is manifest-driven (`id`, `version`, ports, controllers, parameters, runtime metadata).
- Data connections and controller connections are distinct and must match type + direction contracts.
- Controller connector shape is rhomboidal and used for behavior/config wiring rather than standard data flow.
- `accepts_multiple` inputs/controllers require list aggregation behavior in execution.
- Terminal output nodes publish final outputs and are not required to feed downstream nodes.

## 4. Item Preview Policy (Inspect/Load Nodes)

For nodes that inspect or load items:

- Preview items without workflow execution when source data is directly inspectable from node parameters (for example browser-selected files/folders).
- If pre-run preview is available, UI should prompt user selection rather than requiring a run.
- Display only basename (and optional extension); do not display full local file paths in preview lists.
- Runtime-produced items still populate the same item viewer when execution data is available.

## 5. Embedding Output Contract (`vectors`, not `points`)

`TEXT_EMBEDDING` standardized output port:

- Output name: `vectors`
- Output type: `VECTOR_POINT_LIST`
- Meaning: dense numeric embedding arrays (`vector`) with source identifiers and metadata used for semantic similarity search/storage.

Migration compatibility:

- Legacy `points` references may be accepted by compatibility paths during transition.
- New manifests and new workflows must use `vectors`.

## 6. Controller Connector Contracts

### 6.1 `TEXT_EMBEDDING`

- Provides a controller source handle (`embedding`) on the right side.
- Controller payload includes embedding provider/model context and generated vectors.
- This allows direct controller wiring into vector stores for immediate persistence.

### 6.2 `LANCE_DB`

- Accepts controller target handle (`embedding`) for controller-driven vector-save behavior.
- Provides controller source handle (`store`) for downstream retrieval nodes.
- Supports both direct data input (`vectors`) and controller-driven save flow (`TEXT_EMBEDDING -> LANCE_DB`).

### 6.3 `SIMILARITY_SEARCH`

- Accepts controller target handle (`embedding`) to ensure query embedding uses the same embedder context.
- Accepts controller target handle (`store`) for vector store source selection.
- Vector store controller is required.

## 7. Global Node Semantics

Supported global categories:

- model provider (`MODEL_PROVIDER`)
- database provider (`database` category nodes)
- vector store (`vector_storage` category nodes)

Rules:

- At most one global node per global category.
- Explicit controller connections always take precedence over globals.
- If a compatible required controller connection is missing, compiler may inject global node usage implicitly.
- Synthetic implicit links are compile/runtime behavior and are not rendered as canvas edges.

## 8. Retrieval Category: `SIMILARITY_SEARCH`

Initial retrieval node contract:

- Category: `retrieval`
- Data input: `query` (`TEXT`)
- Controller inputs:
  - `embedding` (required)
  - `store` (required)
- Output: `results` (`RETRIEVAL_RESULTS`) containing scored hits and optional metadata.

Config parameters:

- `similarity_strategy`: `cosine`, `euclidean`, `dot` (must match store metric).
- `ann_search_depth` (ANN tuning): default `100`, bounded numeric control.
  - Higher depth generally improves recall with higher latency.
  - Used as adapter-level search depth and mapped to backend-specific knobs where supported (for example HNSW `ef_search` / IVF `nprobe`).
- `top_k`: default `5`, bounded numeric control.
  - Controls result count returned to downstream nodes.
- `score_threshold`: optional normalized threshold when backend adapter supports threshold filtering.
- `include_metadata`: boolean toggle.

Adapter behavior:

- If a backend cannot apply a specific ANN tuning knob directly, use safe fallback behavior and preserve deterministic output contract.

## 9. Import and Catalog API

- Catalog: `GET /nodes/catalog`
- Manifest import: `POST /nodes/import`

Imported manifests must validate against backend schema (`NodeManifest`) before registration.

## 10. Change Management

When adding or modifying a node:

1. Update/create manifest JSON in `ParaGraph/resources/nodes`.
2. Implement or map runtime executor behavior.
3. Update compiler/runtime tests for new contract behavior.
4. Update this file (inventory + summary + contracts) in the same change.
