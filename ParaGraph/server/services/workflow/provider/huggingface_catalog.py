from __future__ import annotations

from ParaGraph.server.domain.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.domain.node_catalog import HuggingFaceModelCatalogResponse, HuggingFaceSortBy, ModelVisibilityFilter


class HuggingFaceCatalogService:
    def __init__(self, provider_service: object) -> None:
        self._provider_service = provider_service

    def list_models(
        self,
        *,
        session_name: str = DEFAULT_SESSION_NAME,
        search: str | None = None,
        task: str | None = None,
        library: str | None = None,
        author: str | None = None,
        visibility: ModelVisibilityFilter = "all",
        sort: HuggingFaceSortBy = "relevance",
        page: int = 1,
        page_size: int = 20,
        refresh: bool = False,
    ) -> HuggingFaceModelCatalogResponse:
        return self._provider_service._list_huggingface_models_impl(  # noqa: SLF001
            session_name=session_name,
            search=search,
            task=task,
            library=library,
            author=author,
            visibility=visibility,
            sort=sort,
            page=page,
            page_size=page_size,
            refresh=refresh,
        )

