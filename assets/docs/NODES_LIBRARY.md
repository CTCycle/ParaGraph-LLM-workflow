# NODES_LIBRARY

Last updated: 2026-05-16

## Purpose

This document describes the node system used by ParaGraph workflows, how nodes are cataloged, and how custom node manifests are imported.

## Node Catalog Sources

- Built-in node manifests are loaded from `app/resources/nodes`.
- Custom node manifests can be imported at runtime from the Nodes page (`/nodes`) using JSON payloads.
- The backend catalog API is `GET /nodes/catalog`.

## Core Node Categories

The frontend and backend organize nodes by category (for example):

- `input`
- `web`
- `prompt`
- `model`
- `memory`
- `retrieval`
- `embeddings`
- `processing`
- `text_segmentation`
- `output`
- `serialization`
- `database`
- `vector_storage`
- `control`

Category labels and ordering are defined in `app/client/src/workflow/schema/nodeCategory.ts`.

## Node Manifest Model

A node manifest includes:

- Identity: `id`, `version`, `name`, `category`, `description`
- Interface: `inputs`, `outputs`, optional `controllers`
- Parameters: typed parameter definitions and optional constraints/defaults
- UI metadata: visual defaults such as width/accent/icon/collapsed state
- Runtime metadata: executor key, cacheability, determinism, side effects, and optional plugin metadata

Runtime validation occurs through backend node registry logic before use in execution plans.

## Similarity Search Contract

- `search_mode`
  - options: `vector`, `keyword`, `hybrid`
- `search_engine`
  - options: `native`, `faiss_augmented`
- `similarity_strategy`
  - options: `cosine`, `euclidean`, `dot`

## Processing and Retrieval Nodes

### Tokenizer

`TOKENIZER` version 2 tokenizes text, documents, document lists, chunks, and chunk lists through Hugging Face `AutoTokenizer.from_pretrained`. It preserves input order and emits structured `TOKENIZER_OUTPUT` or serialized text.

### Metadata

`METADATA` attaches structured metadata to `DOCUMENT`, `DOCUMENT_LIST`, `CHUNK`, and `CHUNK_LIST` payloads. It supports merge or replace behavior, global metadata, and per-record metadata keyed by an ID field.

### Vector Store and Vector Collection

`VECTOR_STORE` keeps backend-specific collection, metadata, indexing, and search behavior behind the vector store adapter interface. Handles include backend, collection/index, metric, dimension, embedding provider/model, and index metadata. Backends expose capabilities such as metadata filtering, hybrid search, and FAISS augmentation through `describe_capabilities`.

### Similarity Search

`SIMILARITY_SEARCH` validates the connected vector store metric and embedding source before search. Metadata filters are passed to backends only when supported, and hybrid mode requires a backend that advertises hybrid search support.

## Database Nodes

The database category includes SQL database connection nodes, CRUD create/read/update/delete nodes, and a custom SQL query node. Existing SQL nodes use typed database connection controllers and parameterized SQLAlchemy execution paths.

## Tool Nodes

### Tool Collection

`TOOL_COLLECTION` creates a typed `TOOL_COLLECTION_HANDLE` from inline Python functions, JSON schema tool definitions, signature text, or local `.py` files. Callable signatures are converted into JSON schema parameter definitions.

### Tool Call

`TOOL_CALL` is provider-neutral. It accepts a `MODEL_HANDLE` from `MODEL_PROVIDER` and a `TOOL_COLLECTION_HANDLE`, uses native tool calling when a provider advertises support, and falls back to structured JSON selection otherwise. It is designed for Ollama, Hugging Face, OpenAI, Gemini, and future providers that implement the provider service interface.

## Importing Custom Nodes

### API

- Endpoint: `POST /nodes/import`
- Request body: node manifest JSON
- Response: imported manifest
- Validation failures return HTTP 422

### UI flow

- Open `/nodes`
- Use the custom node import modal
- Paste/validate manifest JSON
- Submit import
- Reload catalog to make the node available in the workflow editor

## Workflow Integration

- Workflow editor (`/`) fetches the catalog and allows drag/drop node placement.
- Compiler validates node existence, version, ports/controllers compatibility, and required inputs.
- Execution resolves node handlers by manifest metadata through the registry.

## Connectivity Checks

Node-level connectivity endpoints:

- `POST /nodes/check-database-connection`
- `POST /nodes/check-vector-store-connection`

These are used by database/vector-store nodes to validate runtime connection settings before execution.

## Operational Notes

- Node manifests are contract-critical: changes to IDs, versions, or ports affect existing workflows.
- Prefer introducing new versions instead of breaking existing version semantics.
- Keep manifest descriptions explicit so the Nodes page remains understandable to end users.

