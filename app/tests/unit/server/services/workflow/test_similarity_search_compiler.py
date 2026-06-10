from __future__ import annotations

from server.domain.workflow_model import WorkflowDefinition
from server.services.workflow.compiler import compiler_service


###############################################################################
def _build_similarity_workflow(
    *,
    search_mode: str,
    search_engine: str,
    similarity_strategy: str,
    distance_metric: str,
) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "schema_version": 2,
            "nodes": [
                {
                    "node_id": "prompt_query",
                    "node_type": "PROMPT",
                    "node_version": 1,
                    "parameters": {"prompt_text": "hello"},
                },
                {
                    "node_id": "embed_query",
                    "node_type": "TEXT_EMBEDDING",
                    "node_version": 1,
                    "parameters": {
                        "provider": "openai",
                        "model_name": "text-embedding-3-small",
                    },
                },
                {
                    "node_id": "store_vectors",
                    "node_type": "VECTOR_STORE",
                    "node_version": 1,
                    "parameters": {
                        "provider": "chroma",
                        "index_name": "docs",
                        "distance_metric": distance_metric,
                        "write_mode": "overwrite",
                        "storage_path": "vectorstores/test",
                    },
                },
                {
                    "node_id": "similarity",
                    "node_type": "SIMILARITY_SEARCH",
                    "node_version": 1,
                    "parameters": {
                        "search_mode": search_mode,
                        "search_engine": search_engine,
                        "similarity_strategy": similarity_strategy,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "prompt_query",
                    "from_output": "text",
                    "to_node": "embed_query",
                    "to_input": "text",
                },
                {
                    "from_node": "embed_query",
                    "from_output": "vectors",
                    "to_node": "store_vectors",
                    "to_input": "vectors",
                },
                {
                    "from_node": "prompt_query",
                    "from_output": "text",
                    "to_node": "similarity",
                    "to_input": "query",
                },
                {
                    "from_node": "embed_query",
                    "from_controller": "embedding",
                    "to_node": "similarity",
                    "to_controller": "embedding",
                    "connection_type": "controller",
                },
                {
                    "from_node": "store_vectors",
                    "from_controller": "store",
                    "to_node": "similarity",
                    "to_controller": "store",
                    "connection_type": "controller",
                },
            ],
            "metadata": {},
        }
    )


###############################################################################
def test_compiler_reports_similarity_backend_incompatibilities() -> None:
    definition = _build_similarity_workflow(
        search_mode="hybrid",
        search_engine="faiss_augmented",
        similarity_strategy="dot",
        distance_metric="cosine",
    )

    compiled = compiler_service.compile(definition)

    assert compiled.valid is False
    codes = {item.code for item in compiled.diagnostics}
    assert "similarity_metric_mismatch" in codes
    assert "unsupported_similarity_mode" in codes
    assert "unsupported_similarity_engine" in codes
