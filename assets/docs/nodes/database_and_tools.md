# Database And Tools
Last updated: 2026-07-17

## Database Nodes
- The database category includes SQL database connection nodes, CRUD create, read, update, delete, and upsert nodes, plus a custom SQL node.
- Connection engines are reused through a bounded credential-safe registry and disposed at application shutdown. Passwords are replaced by opaque process-local credential references before connection handles are emitted.
- `read_only` is enforced in the repository for every write operation. Custom SQL separates statement text from named bind parameters, rejects multiple statements, and can require query-only execution.
- Table and schema identifiers are validated. PostgreSQL schemas are explicit; SQLite ignores schema selection.
- Reads use bounded limit/offset pagination with deterministic primary-key ordering by default and return total-count and `has_more` metadata.
- Result envelopes consistently expose operation, rows, row count, affected rows, generated identifiers, pagination, and error fields.
- Bulk create, update, and delete repository operations are bounded at 1,000 items and transactionally roll back as a unit on failure.
- Upsert supports explicit conflict columns on SQLite and PostgreSQL. Update and delete support optional version-column checks for optimistic concurrency.

## Transaction Boundary
- Each individual CRUD/custom-SQL operation runs in an explicit database transaction.
- Each bulk repository operation shares one transaction across its complete batch.
- The executor does not currently provide a graph-wide transaction handle across separate nodes; workflows must not assume cross-node atomicity.

## Tool Collection
- `TOOL_COLLECTION` creates a typed `TOOL_COLLECTION_HANDLE`.
- Sources can include inline Python functions, JSON Schema tool definitions, signature text, or local `.py` files.
- Callable signatures are converted into JSON Schema parameter definitions.

## Tool Call
- `TOOL_CALL` is provider-neutral.
- It accepts a `MODEL_HANDLE` from `MODEL_PROVIDER` and a `TOOL_COLLECTION_HANDLE`.
- It uses native tool calling when a provider advertises support and falls back to structured JSON selection otherwise.
- The node is intended to work across Ollama, Hugging Face, OpenAI, Gemini, and future providers that implement the provider service interface.
