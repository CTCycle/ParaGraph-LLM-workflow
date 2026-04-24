# NODES_LIBRARY

Last updated: 2026-04-24

## Purpose

This document describes the node system used by ParaGraph workflows, how nodes are cataloged, and how custom node manifests are imported.

## Node Catalog Sources

- Built-in node manifests are loaded from `ParaGraph/resources/nodes`.
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

Category labels and ordering are defined in `ParaGraph/client/src/workflow/schema/nodeCategory.ts`.

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
  - options: `vector`, `hybrid`
- `search_engine`
  - options: `native`, `faiss_augmented`
- `similarity_strategy`
  - options: `cosine`, `euclidean`, `dot`

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
