from __future__ import annotations

from typing import Any, Protocol

from ParaGraph.server.entities.nodecatalog import (
    ConfigFieldSchema,
    NodeCatalogResponse,
    NodeDefinition,
    NodeExecutionSemantics,
    PortSchema,
)


class NodeCompilerHook(Protocol):
    def __call__(self, node_config: dict[str, Any]) -> dict[str, Any]: ...


class NodeRuntimeHook(Protocol):
    def __call__(self, resolved_config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]: ...


class NodeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, NodeDefinition] = {}
        self._register_defaults()

    def register(self, definition: NodeDefinition) -> None:
        self._definitions[definition.type] = definition

    def get(self, node_type: str) -> NodeDefinition | None:
        return self._definitions.get(node_type)

    def list(self) -> list[NodeDefinition]:
        return sorted(self._definitions.values(), key=lambda item: (item.category, item.label))

    def catalog_response(self) -> NodeCatalogResponse:
        return NodeCatalogResponse(nodes=self.list())

    def _register_defaults(self) -> None:
        process_semantics = NodeExecutionSemantics(
            purity="pure",
            scheduling="async",
            determinism="provider_dependent",
            cacheable=False,
            streamable=True,
            retryable=True,
            emits_artifacts=False,
            requires_secrets=False,
        )

        self.register(
            NodeDefinition(
                type="Prompt",
                version=1,
                label="Prompt",
                description="Input prompt template text",
                category="input",
                ports=[
                    PortSchema(handle="prompt_out", label="Prompt", direction="output", data_type="string"),
                ],
                config_schema=[
                    ConfigFieldSchema(
                        key="text",
                        label="Prompt",
                        field_type="textarea",
                        required=True,
                        default="",
                        description="Text sent downstream to model nodes.",
                    )
                ],
                semantics=NodeExecutionSemantics(
                    purity="pure",
                    scheduling="sync",
                    determinism="deterministic",
                    cacheable=True,
                    streamable=False,
                    retryable=False,
                    emits_artifacts=False,
                    requires_secrets=False,
                ),
            )
        )

        self.register(
            NodeDefinition(
                type="LLM",
                version=1,
                label="LLM",
                description="Generic LLM node with provider/model selection",
                category="process",
                ports=[
                    PortSchema(handle="prompt_in", label="Prompt", direction="input", data_type="string"),
                    PortSchema(handle="response_out", label="Response", direction="output", data_type="string"),
                ],
                config_schema=[
                    ConfigFieldSchema(
                        key="provider",
                        label="Provider",
                        field_type="select",
                        default="ollama",
                        options=["ollama", "openai", "anthropic", "gemini", "huggingface"],
                    ),
                    ConfigFieldSchema(key="model", label="Model", field_type="text", default="llama3.2"),
                    ConfigFieldSchema(key="system_prompt", label="System Prompt", field_type="textarea", default=""),
                    ConfigFieldSchema(
                        key="response_format",
                        label="Response Format",
                        field_type="select",
                        default="text",
                        options=["text", "json"],
                    ),
                    ConfigFieldSchema(key="temperature", label="Temperature", field_type="number", default=0.2),
                    ConfigFieldSchema(key="max_tokens", label="Max Tokens", field_type="number", default=512),
                ],
                semantics=process_semantics,
            )
        )

        self.register(
            NodeDefinition(
                type="Retrieval",
                version=1,
                label="Retrieval",
                description="Retrieve context from a knowledge source",
                category="process",
                ports=[
                    PortSchema(handle="query_in", label="Query", direction="input", data_type="string"),
                    PortSchema(handle="context_out", label="Context", direction="output", data_type="document[]"),
                ],
                config_schema=[
                    ConfigFieldSchema(key="knowledge_source", label="Knowledge Source", field_type="text", default="local"),
                    ConfigFieldSchema(key="top_k", label="Top K", field_type="number", default=4),
                ],
                semantics=NodeExecutionSemantics(
                    purity="pure",
                    scheduling="async",
                    determinism="provider_dependent",
                    cacheable=True,
                    streamable=False,
                    retryable=True,
                    emits_artifacts=True,
                    requires_secrets=False,
                ),
            )
        )

        self.register(
            NodeDefinition(
                type="VectorDB",
                version=1,
                label="Vector Store Query",
                description="Query vector store and return ranked snippets",
                category="process",
                ports=[
                    PortSchema(handle="query_in", label="Query", direction="input", data_type="string"),
                    PortSchema(handle="context_out", label="Context", direction="output", data_type="document[]"),
                ],
                config_schema=[
                    ConfigFieldSchema(key="provider", label="Provider", field_type="select", default="local", options=["local", "qdrant", "chroma", "pgvector"]),
                    ConfigFieldSchema(key="index_name", label="Index", field_type="text", default="default"),
                ],
                semantics=NodeExecutionSemantics(
                    purity="pure",
                    scheduling="async",
                    determinism="provider_dependent",
                    cacheable=True,
                    streamable=False,
                    retryable=True,
                    emits_artifacts=True,
                    requires_secrets=False,
                ),
            )
        )

        self.register(
            NodeDefinition(
                type="Output",
                version=1,
                label="Output",
                description="Terminal output node",
                category="output",
                ports=[
                    PortSchema(handle="text_in", label="Text", direction="input", data_type="string"),
                ],
                config_schema=[
                    ConfigFieldSchema(
                        key="outputText",
                        label="Output",
                        field_type="textarea",
                        required=False,
                        default="",
                        description="Runtime output snapshot. Not persisted into workflow definition.",
                    )
                ],
                semantics=NodeExecutionSemantics(
                    purity="pure",
                    scheduling="sync",
                    determinism="deterministic",
                    cacheable=False,
                    streamable=False,
                    retryable=False,
                    emits_artifacts=True,
                    requires_secrets=False,
                ),
            )
        )


node_registry = NodeRegistry()
