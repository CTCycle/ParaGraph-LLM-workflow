# Database And Tools
Last updated: 2026-06-02

## Database Nodes
- The database category includes SQL database connection nodes, CRUD create, read, update, and delete nodes, plus a custom SQL query node.
- Existing SQL nodes use typed database connection controllers and parameterized SQLAlchemy execution paths.

## Tool Collection
- `TOOL_COLLECTION` creates a typed `TOOL_COLLECTION_HANDLE`.
- Sources can include inline Python functions, JSON Schema tool definitions, signature text, or local `.py` files.
- Callable signatures are converted into JSON Schema parameter definitions.

## Tool Call
- `TOOL_CALL` is provider-neutral.
- It accepts a `MODEL_HANDLE` from `MODEL_PROVIDER` and a `TOOL_COLLECTION_HANDLE`.
- It uses native tool calling when a provider advertises support and falls back to structured JSON selection otherwise.
- The node is intended to work across Ollama, Hugging Face, OpenAI, Gemini, and future providers that implement the provider service interface.
