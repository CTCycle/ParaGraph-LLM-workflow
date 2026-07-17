# Catalog And Manifests
Last updated: 2026-07-17

## Purpose
This branch documents the ParaGraph node system, the node catalog, and the contracts that allow nodes to participate in workflow compilation and execution.

## Node Catalog Sources
- Built-in node manifests are loaded from `app/resources/nodes`.
- Custom manifests can be imported at runtime from `/nodes` using JSON payloads.
- The backend catalog endpoint is `GET /nodes/catalog`.

## Core Node Categories
The frontend and backend organize nodes by category, including:

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

- Identity fields such as `id`, `version`, `name`, `category`, and `description`
- Interface definitions such as `inputs`, `outputs`, and optional `controllers`
- Parameter definitions with types, defaults, and constraints
- UI metadata such as width, accent, icon, and collapsed state
- Runtime metadata such as executor key, cacheability, determinism, side effects, and optional plugin metadata

Runtime validation happens through backend node registry logic before nodes are admitted into execution plans.

Manifest contract validation rejects duplicate input, output, controller, and
parameter names. During execution, handlers must return an object containing
only outputs or source controllers declared by the manifest, and every required
output must be present.

## Compatibility Rules
- Node manifests are contract-critical.
- Changes to IDs, versions, ports, or controller contracts can break existing workflows.
- Workflow and visual graph schema versions are explicit and currently fixed at version 2.
- Prefer adding new versions instead of changing node version semantics in place.
- Keep manifest descriptions explicit so the Nodes page remains understandable to end users.
