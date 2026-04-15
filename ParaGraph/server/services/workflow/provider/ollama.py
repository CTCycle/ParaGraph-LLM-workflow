from __future__ import annotations

from ParaGraph.server.domain.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.domain.node_catalog import OllamaLibraryCatalogResponse, OllamaModelPullResponse


class OllamaLibraryService:
    def __init__(self, provider_service: object) -> None:
        self._provider_service = provider_service

    def list_models(
        self,
        *,
        session_name: str = DEFAULT_SESSION_NAME,
        search: str | None = None,
        refresh: bool = False,
    ) -> OllamaLibraryCatalogResponse:
        return self._provider_service._list_ollama_library_models_impl(  # noqa: SLF001
            session_name=session_name,
            search=search,
            refresh=refresh,
        )

    def pull_model(
        self,
        *,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> OllamaModelPullResponse:
        return self._provider_service._pull_ollama_model_impl(  # noqa: SLF001
            model=model,
            session_name=session_name,
        )

