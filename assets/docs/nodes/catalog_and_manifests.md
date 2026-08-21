# Catalog And Manifests
Last updated: 2026-08-21

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

## Chat Nodes
`app/resources/nodes/chat_input_v1.json` defines the `CHAT_INPUT` node. It has
one transient `text` output and a required `history` controller connection to
`CHAT_HISTORY_MEMORY` or `CHAT_HISTORY_PERSISTED`. The editor keeps the message
in the Chat node controls only long enough to submit the current run; it is not
written into the saved workflow definition.

The compiler requires every Chat node to reach exactly one `output` node through
data connections. Multiple Chat nodes therefore have separate terminal-output
associations and separate history scopes.

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

## Persistence Ownership
- The configured filesystem resource root is the sole source of truth for node
  manifests, including imported custom manifests and built-in assets.
- `server/repositories/workflow/node_manifest.py` owns manifest file writes,
  reloads, and rollback deletion. The application database does not mirror
  manifests in a `nodes` table.
- Changes to manifest persistence must preserve the write-then-reload
  validation boundary so a failed import cannot leave an invalid manifest on
  disk.
