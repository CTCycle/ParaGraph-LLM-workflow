# Import And Integration
Last updated: 2026-06-02

## Custom Node Import API
- Endpoint: `POST /nodes/import`
- Request body: node manifest JSON
- Response: imported manifest
- Validation failures return HTTP 422

## UI Import Flow
1. Open `/nodes`.
2. Open the custom node import modal.
3. Paste and validate manifest JSON.
4. Submit the import.
5. Reload the catalog so the node becomes available in the workflow editor.

## Workflow Integration
- The workflow editor at `/` fetches the node catalog and supports drag and drop placement.
- The compiler validates node existence, version, ports and controllers compatibility, and required inputs.
- Execution resolves node handlers from manifest metadata through the backend registry.

## Connectivity Checks
Node-level connectivity endpoints:

- `POST /nodes/check-database-connection`
- `POST /nodes/check-vector-store-connection`

These are used by database and vector-store nodes to validate runtime connection settings before execution.

## Operational Notes
- Keep custom manifests explicit and versioned with care.
- Connectivity checks validate environment assumptions before runtime execution, but do not replace compile-time graph validation.
