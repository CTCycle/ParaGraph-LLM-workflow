from __future__ import annotations

from datetime import datetime, timezone
import time

from bs4 import BeautifulSoup
import httpx

from server.domain.provider import CachedValue, OllamaLibraryCachePayload
from server.services.llm.providers import OllamaError
from server.services.workflow.provider.constants import (
    OLLAMA_LIBRARY_CACHE_TTL_SECONDS,
    OLLAMA_LIBRARY_URL,
)
from server.services.workflow.provider.errors import ProviderApiError
from server.services.workflow.provider.helpers import (
    _model_basename,
    _normalize_ollama_library_slug,
)
from server.domain.configuration import DEFAULT_SESSION_NAME
from server.domain.node_catalog import (
    OllamaLibraryCatalogResponse,
    OllamaModelPullResponse,
)


class OllamaLibraryCatalogMixin:
    def _load_ollama_library_catalog(
        self, *, refresh: bool
    ) -> OllamaLibraryCachePayload:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._ollama_library_cache
            if not refresh and cached and cached.expires_at > now:
                payload = cached.value
                if isinstance(payload, OllamaLibraryCachePayload):
                    return payload

        payload = self._fetch_ollama_library_catalog()
        with self._cache_lock:
            self._ollama_library_cache = CachedValue(
                value=payload,
                expires_at=time.monotonic() + OLLAMA_LIBRARY_CACHE_TTL_SECONDS,
            )
        return payload

    def _fetch_ollama_library_catalog(self) -> OllamaLibraryCachePayload:
        try:
            response = httpx.get(
                OLLAMA_LIBRARY_URL,
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": "ParaGraph/0.1"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderApiError(
                "Timed out while fetching Ollama library models.",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderApiError(
                f"Ollama library request failed ({exc.response.status_code}).",
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderApiError(
                f"Unable to reach Ollama library: {exc}",
                status_code=503,
            ) from exc

        soup = BeautifulSoup(response.text, "html.parser")
        discovered: dict[str, str | None] = {}
        for anchor in soup.select('a[href^="/library/"]'):
            href = str(anchor.get("href") or "")
            slug = _normalize_ollama_library_slug(href)
            if not slug:
                continue
            label_text = anchor.get_text(" ", strip=True)
            description = (
                label_text if label_text and label_text.lower() != slug else None
            )
            discovered.setdefault(slug, description)

        if not discovered:
            raise ProviderApiError(
                "Unable to parse model rows from Ollama library response.",
                status_code=502,
            )

        ordered = tuple((name, discovered[name]) for name in sorted(discovered))
        refreshed_at = datetime.now(timezone.utc).isoformat()
        return OllamaLibraryCachePayload(models=ordered, refreshed_at=refreshed_at)

    def _get_pulled_ollama_model_names(self, session_name: str) -> set[str]:
        try:
            pulled = self._ollama_client(session_name).list_models()
        except ValueError, OllamaError:
            return set()

        normalized: set[str] = set()
        for item in pulled:
            name = item.strip().lower()
            if not name:
                continue
            normalized.add(name)
            normalized.add(_model_basename(name))
        return normalized


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
