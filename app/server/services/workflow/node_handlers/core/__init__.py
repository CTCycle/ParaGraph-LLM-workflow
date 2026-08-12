from __future__ import annotations

from server.domain.node_handler import NodeHandler
from server.domain.node_handler_core import (
    ChatParameters,
    EmbeddingParameters,
    InMemoryChatHistoryParameters,
    ModelProviderParameters,
    PersistedChatHistoryParameters,
    PromptParameters,
    PromptTemplateParameters,
    RerankParameters,
    SaveAsFileParameters,
    SaveAsFolderParameters,
    SimilaritySearchParameters,
    StorageParameters,
    StructuredParameters,
    TokenizerParameters,
    VectorStoreParameters,
    VectorStoreLifecycleParameters,
)
from server.services.workflow.node_handlers.core.chat_history import (
    execute_chat_history_memory,
    execute_chat_history_persisted,
)
from server.services.workflow.node_handlers.core.embeddings import (
    _embedding_executor,
    _rerank_results_executor,
    _similarity_search_executor,
    _vector_store_executor,
    _vector_store_lifecycle_executor,
)
from server.services.workflow.node_handlers.core.models import (
    _llm_chat_executor,
    _llm_structured_executor,
    _model_provider_executor,
)
from server.services.workflow.node_handlers.core.prompts import (
    _prompt_executor,
    _prompt_template_executor,
)
from server.services.workflow.node_handlers.core.routing import _tokenize_executor
from server.services.workflow.node_handlers.core.storage import (
    _load_text_executor,
    _save_as_file_executor,
    _save_as_folder_executor,
)


CORE_HANDLERS = {
    "prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "prompt_template": NodeHandler(
        executor=_prompt_template_executor, parameter_model=PromptTemplateParameters
    ),
    "model_provider": NodeHandler(
        executor=_model_provider_executor, parameter_model=ModelProviderParameters
    ),
    "llm_chat": NodeHandler(
        executor=_llm_chat_executor, parameter_model=ChatParameters
    ),
    "llm_structured": NodeHandler(
        executor=_llm_structured_executor, parameter_model=StructuredParameters
    ),
    "text_embedding": NodeHandler(
        executor=_embedding_executor, parameter_model=EmbeddingParameters
    ),
    "vector_store": NodeHandler(
        executor=_vector_store_executor, parameter_model=VectorStoreParameters
    ),
    "vector_store_lifecycle": NodeHandler(
        executor=_vector_store_lifecycle_executor,
        parameter_model=VectorStoreLifecycleParameters,
    ),
    "similarity_search": NodeHandler(
        executor=_similarity_search_executor, parameter_model=SimilaritySearchParameters
    ),
    "rerank_results": NodeHandler(
        executor=_rerank_results_executor, parameter_model=RerankParameters
    ),
    "tokenize": NodeHandler(
        executor=_tokenize_executor, parameter_model=TokenizerParameters
    ),
    "save_as_file": NodeHandler(
        executor=_save_as_file_executor, parameter_model=SaveAsFileParameters
    ),
    "save_as_folder": NodeHandler(
        executor=_save_as_folder_executor, parameter_model=SaveAsFolderParameters
    ),
    "load_text": NodeHandler(
        executor=_load_text_executor, parameter_model=StorageParameters
    ),
    "chat_history_memory": NodeHandler(
        executor=execute_chat_history_memory,
        parameter_model=InMemoryChatHistoryParameters,
    ),
    "chat_history_persisted": NodeHandler(
        executor=execute_chat_history_persisted,
        parameter_model=PersistedChatHistoryParameters,
    ),
}

__all__ = ["CORE_HANDLERS"]
