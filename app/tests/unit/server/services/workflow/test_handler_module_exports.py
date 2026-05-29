from __future__ import annotations

from server.services.workflow import compiler_service, node_registry, provider_service
from server.services.workflow.node_handlers import (
    ADDITIONAL_CORE_NODE_HANDLERS,
    NODE_HANDLERS,
)
from server.services.workflow.node_handlers.advanced_text import ADVANCED_TEXT_HANDLERS
from server.services.workflow.node_handlers.control import CONTROL_HANDLERS
from server.services.workflow.node_handlers.core import CORE_HANDLERS
from server.services.workflow.node_handlers.database import DATABASE_HANDLERS
from server.services.workflow.node_handlers.http import HTTP_HANDLERS
from server.services.workflow.node_handlers.ingestion import (
    INGESTION_HANDLERS,
    load_file_text,
    resolve_local_path,
)
from server.services.workflow.node_handlers.processing import PROCESSING_HANDLERS
from server.services.workflow.node_handlers.rag import RAG_HANDLERS
from server.services.workflow.node_handlers.structured import STRUCTURED_HANDLERS
from server.services.workflow.provider import ProviderApiError


def test_service_package_exports_remain_stable() -> None:
    assert compiler_service is not None
    assert provider_service is not None
    assert node_registry is not None
    assert ProviderApiError.__name__ == "ProviderApiError"
    assert callable(load_file_text)
    assert callable(resolve_local_path)


def test_handler_registries_keep_expected_keys() -> None:
    assert set(CORE_HANDLERS) == {
        "prompt",
        "prompt_template",
        "image_input",
        "model_provider",
        "llm_chat",
        "llm_structured",
        "text_embedding",
        "vector_store",
        "similarity_search",
        "rerank_results",
        "tokenize",
        "text_split",
        "save_as_file",
        "save_as_folder",
        "load_text",
        "if",
        "router",
        "chat_history_memory",
        "chat_history_persisted",
    }
    assert set(PROCESSING_HANDLERS) == {
        "fixed_size_chunks",
        "by_delimiter_chunks",
        "by_structure_chunks",
        "regex_split_chunks",
        "recursive_split_chunks",
            "sentence_window_chunks",
            "merge_small_chunks",
            "normalize_text",
            "regex_extract",
            "regex_replace",
            "token_split_chunks",
            "semantic_split_chunks",
            "join_merge_text",
            "deduplicate_text",
            "metadata_attach",
            "language_detect",
            "token_counter",
            "truncate_to_budget",
            "llm_summarize",
            "llm_rewrite",
    }
    assert set(INGESTION_HANDLERS) == {
        "directory_loader",
        "document_text_extractor",
        "load_documents",
        "sql_database",
        "sql_file_database",
    }
    assert set(DATABASE_HANDLERS) == {
        "crud_create",
        "crud_read",
        "crud_update",
        "crud_delete",
        "custom_sql_query",
    }
    assert set(NODE_HANDLERS) == (
        set(CORE_HANDLERS)
        | set(ADDITIONAL_CORE_NODE_HANDLERS)
        | set(PROCESSING_HANDLERS)
        | set(INGESTION_HANDLERS)
        | set(DATABASE_HANDLERS)
        | set(STRUCTURED_HANDLERS)
        | set(RAG_HANDLERS)
        | set(ADVANCED_TEXT_HANDLERS)
        | set(HTTP_HANDLERS)
        | set(CONTROL_HANDLERS)
        | {"text_output", "image_output", "json_output"}
    )
