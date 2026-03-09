export interface NodeArtifactDefinition {
    key: string
    label: string
    description: string
}

export interface NodePrincipleDefinition {
    title: string
    description: string
}

export interface NodeTaxonomyDefinition {
    label: string
    description: string
}

export const WORKFLOW_EXECUTABLE_TYPES = ['Prompt', 'LLM', 'Output'] as const

export const NODE_ARTIFACTS: NodeArtifactDefinition[] = [
    { key: 'messages', label: 'Messages', description: 'Role-tagged turns passed between conversation-aware nodes.' },
    { key: 'prompt-template', label: 'PromptTemplate', description: 'Reusable prompt skeletons with variables and formatting rules.' },
    { key: 'llm-response', label: 'LLMResponse', description: 'Raw model output including text, finish reasons, and provider metadata.' },
    { key: 'tool-invocation', label: 'ToolInvocation', description: 'Structured requests describing which tool to call and with what arguments.' },
    { key: 'tool-result', label: 'ToolResult', description: 'Normalized tool outputs returned to downstream parsing or planning nodes.' },
    { key: 'document-set', label: 'DocumentSet', description: 'Retrieved or ranked context documents bundled with provenance.' },
    { key: 'embedding-vector', label: 'EmbeddingVector', description: 'Numeric representations used for retrieval and semantic matching.' },
    { key: 'retriever-config', label: 'RetrieverConfig', description: 'Search limits, filters, scoring options, and source selection rules.' },
    { key: 'json-schema', label: 'JSONSchema', description: 'Machine-readable validation contracts for structured outputs.' },
    { key: 'structured-object', label: 'StructuredObject<T>', description: 'Parsed and schema-checked JSON objects emitted by extraction nodes.' },
    { key: 'conversation-memory', label: 'ConversationMemory', description: 'Persistent summaries, notes, or episodic memories across runs.' },
    { key: 'decision', label: 'Decision', description: 'Branching signals such as continue, retry, escalate, or stop.' },
    { key: 'score', label: 'Score', description: 'Confidence or evaluator values used for reranking and control flow.' },
    { key: 'control-signal', label: 'ControlSignal', description: 'Pause, resume, retry, and human-approval events flowing through the runtime.' },
]

export const NODE_SYSTEM_PRINCIPLES: NodePrincipleDefinition[] = [
    {
        title: 'Typed Ports',
        description: 'Nodes exchange explicit artifact types instead of generic strings so validation, caching, and reuse stay predictable.',
    },
    {
        title: 'Graph Runtime',
        description: 'Execution belongs to the server: it schedules ready nodes, tracks traces, and replays saved workflow JSON deterministically.',
    },
    {
        title: 'Shared State',
        description: 'Graphs keep raw workflow state separate from prompt formatting so loops, retries, and tool cycles remain inspectable.',
    },
    {
        title: 'Streaming Events',
        description: 'Long-running nodes should emit tokens, tool progress, retries, and human-input pauses so the UI reflects real execution.',
    },
]

export const NODE_TAXONOMY: NodeTaxonomyDefinition[] = [
    { label: 'Inputs', description: 'User messages, file drops, API triggers, and scheduled starts.' },
    { label: 'Context', description: 'Prompt templates, message builders, and memory readers.' },
    { label: 'Retrieval', description: 'Embedding, search, reranking, and chunk selection.' },
    { label: 'Model', description: 'Chat completion, reasoning, and structured extraction.' },
    { label: 'Tooling', description: 'HTTP calls, SQL, code execution, and external app actions.' },
    { label: 'Control', description: 'Branching, retries, loops, map steps, and stop conditions.' },
    { label: 'Validation', description: 'Schema checks, policy filters, and guardrails.' },
    { label: 'Output', description: 'Chat replies, structured writes, webhooks, and memory updates.' },
    { label: 'Debug', description: 'Trace viewers, state inspection, and execution logging.' },
]

export const NODE_CONTRACT_SNIPPET = `metadata:
  id
  name
  version
  category
  description

input ports:
  typed fields
  defaults
  optionality

output ports:
  typed fields

execute(context, inputs, state)
  -> outputs
  -> state updates
  -> emitted events`
