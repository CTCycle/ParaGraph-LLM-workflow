from __future__ import annotations

from server.services.workflow.provider.constants import (
    HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS,
)
from server.services.workflow.provider.errors import ProviderApiError
from server.services.workflow.provider.huggingface_downloads import (
    HuggingFaceDownloadMixin,
)

__all__ = [
    "HuggingFaceDownloadMixin",
    "HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS",
    "ProviderApiError",
    "ProviderService",
    "provider_service",
]


def __getattr__(name: str):
    if name in {"ProviderService", "provider_service"}:
        from server.services.workflow.provider.service import (
            ProviderService,
            provider_service,
        )

        return {
            "ProviderService": ProviderService,
            "provider_service": provider_service,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
