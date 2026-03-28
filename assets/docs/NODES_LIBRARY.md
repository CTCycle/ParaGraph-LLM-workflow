# Nodes Library

Source of truth for available workflow nodes is the manifest set in:

- `ParaGraph/resources/nodes/*.json`

All currently shipped manifests are version `v1`.

## 1. Current Node Inventory

| Category | Node IDs |
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

## 2. Node Summary

- `ASSIGN_NAME`: wraps an upstream value into a named JSON map.
- `PROMPT`: emits fixed prompt text.
- `PROMPT_TEMPLATE`: renders prompt text from template + variables.
- `MODEL_PROVIDER`: emits a typed model-controller handle.
- `LLM_CHAT`: runs chat completion using model handle + prompt input.
- `LLM_STRUCTURED`: runs structured generation using model handle + prompt input.
- `TEXT_EMBEDDING`: produces vectors from text/doc/chunk inputs.
- `LOAD_DOCUMENTS`: reads folder content as document records.
- `LOAD_TEXT`: reads text from a local file path.
- `SAVE_AS_FILE`: serializes text/docs/chunks into one output file.
- `SAVE_AS_FOLDER`: serializes text/docs/chunks into output folder files.
- `FIXED_SIZE_CHUNKS`: fixed-size segmentation.
- `BY_DELIMITER_CHUNKS`: delimiter-based segmentation.
- `BY_STRUCTURE_CHUNKS`: structure-aware segmentation (paragraph/heading style boundaries).
- `RECURSIVE_SPLIT_CHUNKS`: recursive separator fallback segmentation.
- `REGEX_SPLIT_CHUNKS`: regex-based segmentation.
- `SENTENCE_WINDOW_CHUNKS`: sentence-window segmentation with overlap.
- `MERGE_SMALL_CHUNKS`: merges small adjacent fragments.
- `SQL_DATABASE`: creates SQL DB controller handle from connection parameters.
- `SQL_FILE_DATABASE`: creates embedded SQL DB controller handle.
- `LANCE_DB`: stores vector points in local LanceDB table.
- `TEXT_OUTPUT`: terminal text output node.
- `JSON_OUTPUT`: terminal JSON output node.

## 3. Contract Rules

- Node contract validation is manifest-driven (`id`, `version`, ports, parameters, runtime metadata).
- Data connections and controller connections are distinct and must match the compiler/runtime contract.
- `accepts_multiple` inputs/controllers require list aggregation behavior in execution.
- Terminal output nodes publish final outputs and are not required to feed downstream nodes.

## 4. Import and Catalog API

- Catalog: `GET /nodes/catalog`
- Manifest import: `POST /nodes/import`

Imported manifests must validate against backend schema (`NodeManifest`) before registration.

## 5. Change Management

When adding or modifying a node:

1. Update/create manifest JSON in `ParaGraph/resources/nodes`.
2. Implement or map runtime executor behavior.
3. Update compiler/runtime tests for new contract behavior.
4. Update this file (inventory + summary) in the same change.
