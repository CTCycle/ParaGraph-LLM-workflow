# Processing And Retrieval
Last updated: 2026-08-27

## Similarity Search Contract
- `search_mode`
  - `vector`, `keyword`, `hybrid`
- `search_engine`
  - `native`, `faiss_augmented`
- `similarity_strategy`
  - `cosine`, `euclidean`, `dot`

`GET /nodes/catalog` publishes one typed `vector_store_capabilities` entry per
adapter. The editor, compiler, and runtime consume that same contract. A
request is rejected before a backend call when it asks for an unsupported
metric, search mode, search engine, namespace, filter operator, grouped filter,
explicit `minimum_should_match`, or keyword index.

## Named Variables From JSON
When a connected node output is a JSON object, or a JSON string that parses to a JSON object, ParaGraph publishes each top-level key as a downstream named variable. Nested keys and array indexes are not published automatically.

Object outputs are published as their top-level JSON fields for downstream bindings. Scalar outputs remain scalar; there is no output-renaming or collision compatibility layer.

Example structured output:

```json
{
  "summary": "The trial met its primary endpoint.",
  "keywords": ["phase 2", "safety", "efficacy"]
}
```

Template and prompt formatting can reference those fields directly:

```jinja
Summary: {{ summary }}
Keywords: {{ keywords | join(", ") }}
```

HTTP nodes can also use named variables in query parameters or request body templates, or receive a full upstream JSON object as the request body.

## Structured Payload Editing

JSON parameters have an inline literal editor with validation. If a typed input
edge targets the same parameter name, the editor marks the literal as a
fallback: the bound upstream payload is used for that run, while the validated
literal remains available when the edge is removed. Controller edges are
separate from payload bindings and never override JSON parameters.

## Prompt And Structured JSON Nodes
- `PROMPT_TEMPLATE` is presented as Template and Prompt Format.
- It supports Jinja syntax, including `system_template`, `user_template`, `reusable_blocks`, and strict missing-variable validation.
- Prompt templates use Jinja syntax only; legacy `{name}` formatting is not supported.
- `LLM_STRUCTURED` handles structured generation and extraction.
- It returns the main JSON object as `result` plus `schema`, `valid`, and `errors`.
- Validation can use JSON Schema mode, an inferred model, or pasted Pydantic model source parsed without executing arbitrary Python.
- Related structured nodes include `STRUCTURED_INPUT`, `STRUCTURED_OUTPUT`, and `OUTPUT_PARSER`.

## RAG And Document Processing
- Primary document and retrieval extension points are:
  - Load Documents
  - Document Text Extractor
  - Text Embedding
  - Vector Store
  - Similarity Search
  - Rerank Results
- Additional RAG nodes include:
  - `HTML_TO_TEXT`
  - `CHUNK_ENRICHER`
  - `CONTEXT_BUILDER`
  - `CITATION_FORMATTER`

## Text Processing And Advanced Text
Processing coverage includes normalization, regex extraction and replacement, join and merge, deduplication, metadata attachment, claim extraction, contradiction detection, entity extraction and resolution, PII detection and redaction, prompt injection detection, instruction stripping, diffing, table extraction, Markdown parsing, code block extraction, citation extraction, date normalization, and unit and number normalization.

Nodes that previously advertised model-backed, tokenizer-backed, OCR, repair,
dynamic routing, subgraph mapping, batching, or fallback behavior without
implementing those contracts were removed from the production catalog. They
must return as new versioned nodes only with real runtime implementations.

Representative newer manifests include:
- Processing:
  - `NORMALIZE_TEXT`
  - `REGEX_EXTRACT`
  - `REGEX_REPLACE`
  - `JOIN_MERGE_TEXT`
  - `DEDUPLICATE_TEXT`
  - `METADATA_ATTACH`
- Advanced text:
  - `CLAIM_EXTRACTOR`
  - `CONTRADICTION_DETECTOR`
  - `ENTITY_EXTRACTOR`
  - `ENTITY_RESOLVER`
  - `PII_DETECTOR`
  - `PII_REDACTOR`
  - `PROMPT_INJECTION_DETECTOR`
  - `INSTRUCTION_STRIPPER`
  - `DIFF_TEXT`
  - `TABLE_EXTRACTOR`
  - `MARKDOWN_PARSER`
  - `CODE_BLOCK_EXTRACTOR`
  - `CITATION_EXTRACTOR`
  - `DATE_NORMALIZER`
  - `UNIT_NUMBER_NORMALIZER`

## Web API Nodes
- `HTTP_GET`, `HTTP_POST`, `HTTP_PUT`, `HTTP_PATCH`, and `HTTP_DELETE` provide
  explicit method contracts through the shared secure transport.
- `HTTP_REQUEST` remains the advanced multi-method node for HEAD, OPTIONS, or
  workflows that need a dynamic method value.
- Only `http` and `https` schemes are allowed.
- Hostnames are resolved before requests and loopback, private, link-local, multicast, and unspecified addresses are blocked by default.
- Redirects are disabled by default, revalidated on every hop, and HTTPS
  downgrade is forbidden unless explicitly enabled on a trusted local request.
- Request retries are bounded; unsafe methods require an idempotency key or an
  explicit opt-in, and response/download byte limits are enforced while reading.
- Credential profiles resolve secrets at execution time. Secrets and sensitive
  response headers are redacted from returned metadata.

## Control, Tokenizer, Metadata, And Vector Search
- Control nodes include `IF_TEXT_CONTAINS`, `REDUCE_CHUNKS`, `CACHE_NODE`, `HUMAN_REVIEW_GATE`, and `TRACE_DEBUG_VIEWER`.
- Execution state supports `skipped` steps and `paused` runs for human review workflows.
- `TOKENIZER` version 2 tokenizes text, documents, document lists, chunks, and chunk lists through Hugging Face `AutoTokenizer.from_pretrained`.
- It preserves input order and emits structured `TOKENIZER_OUTPUT` or serialized text.
- `METADATA` attaches structured metadata to `DOCUMENT`, `DOCUMENT_LIST`, `CHUNK`, and `CHUNK_LIST` payloads with merge or replace behavior.
- `VECTOR_STORE` hides backend-specific collection, metadata, indexing, and search behavior behind the vector store adapter interface.
- Vector store handles include backend, collection or index, metric, namespace,
  dimension, embedding provider and model, and index metadata.
- Retrieval hits expose `score_semantics`: cosine and L2 scores are
  `normalized_similarity` where the adapter can normalize the provider score;
  dot-product scores remain explicit `native_similarity` because they are
  unbounded.
- `SIMILARITY_SEARCH` validates vector store metric and embedding source before
  search. Unsupported capability requests fail closed instead of dropping a
  filter clause or silently changing search semantics.

## Vector Store Lifecycle Contract
- `VECTOR_STORE` version 2 defines explicit `reject` and `upsert` duplicate-ID policies. Insert-style writes reject conflicts; upserts deterministically replace matching record IDs.
- Vector records persist source document and chunk ownership plus embedding provider, model, optional revision, dimension, normalization behavior, and native distance metric. Appends and searches reject incompatible contracts before a backend call.
- `VECTOR_STORE_LIFECYCLE` exposes update, delete-by-ID, delete-by-document, metadata-filter deletion where supported, collection inspection/deletion, and reload. Results contain affected IDs and counts; unsupported adapter operations return a stable explicit error.
- FAISS writes build a complete temporary sibling store under a per-index bounded file lock, then atomically replace the committed directory. A failed build removes temporary state and preserves the last committed index.
- LanceDB uses its versioned native table commits plus a per-table bounded writer lock. Chroma configures its native HNSW metric and stores structured metadata as JSON because Chroma metadata values are scalar.
- Shared filters provide equality, membership, existence, containment, and range
  clauses. Each adapter advertises its supported operators. Remote dialects
  that cannot express `exists`, `contains`, or explicit
  `minimum_should_match` reject those requests rather than dropping clauses.
  Client-side filtering over-fetches at most five times the requested limit and
  applies the final limit after filtering where the adapter supports it.
- Recursive chunking applies `chunk_overlap` after separator recursion as well
  as during fixed-size fallback, using the configured words, tokens, or
  characters unit.
- Remote credentials are resolved from a saved configuration profile at execution time. Handles contain only a bounded runtime secret handle and the profile reference, never the resolved API key.

## Vector Backend Validation Matrix
- FAISS: local insert/upsert, duplicate conflict, compatibility rejection, search/filter, update, document deletion, inspection, reload, collection deletion, and last-good-state behavior executed.
- LanceDB: local write, inspection, update/delete primitives, reload, and collection deletion executed with native versioned storage.
- Chroma: local write, native metric configuration, inspection, document deletion, reload, and collection deletion executed.
- Qdrant, Pinecone, Weaviate, and Milvus: dialect-aware implementation and supplemental contract coverage only in the baseline environment; no external service runtime claim is made.

### Capability Matrix

| Backend | Metrics | Search modes | Namespaces | Filter operators | Explicit minimum_should_match |
| --- | --- | --- | --- | --- | --- |
| FAISS, LanceDB, Chroma | cosine, l2, dot | vector | no | all shared operators | yes |
| Qdrant, Pinecone, Milvus | cosine, l2, dot | vector | Pinecone only | eq, in, gt, gte, lt, lte | no |
| Weaviate | cosine | vector | no | all shared operators (client-side) | yes |

`faiss_augmented` is an explicitly cataloged local FAISS engine alias; other
adapters expose only `native`. The matrix describes code-level contracts and
mocked/supplemental coverage. It does not claim that an external provider
service was reachable in the validation environment.
