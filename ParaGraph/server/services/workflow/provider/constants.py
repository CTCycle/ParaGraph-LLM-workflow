from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from ParaGraph.server.common.constants import MODELS_PATH
from ParaGraph.server.domain.node_catalog import HuggingFaceSortBy


OLLAMA_LIBRARY_URL: Final[str] = "https://ollama.com/library"
OLLAMA_LIBRARY_CACHE_TTL_SECONDS: Final[float] = 300.0
HUGGINGFACE_CACHE_TTL_SECONDS: Final[float] = 45.0
HUGGINGFACE_FILTER_TAGS_CACHE_TTL_SECONDS: Final[float] = 3600.0
HUGGINGFACE_MAX_FETCH_LIMIT: Final[int] = 500
HUGGINGFACE_MAX_PAGE_SIZE: Final[int] = 50
HUGGINGFACE_LOCAL_MODELS_ROOT: Final[Path] = Path(MODELS_PATH) / "huggingface"
HUGGINGFACE_LOCAL_MODEL_METADATA_FILE: Final[str] = ".paragraph-model.json"
HUGGINGFACE_REPO_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"
)
HUGGINGFACE_DOWNLOAD_JOB_TYPE: Final[str] = "huggingface_download"
HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 60.0

HUGGINGFACE_SORT_FIELD_MAP: Final[dict[HuggingFaceSortBy, str | None]] = {
    "relevance": None,
    "downloads": "downloads",
    "likes": "likes",
    "updated": "lastModified",
}

HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS: Final[tuple[str, ...]] = (
    "author",
    "downloads",
    "gated",
    "lastModified",
    "library_name",
    "likes",
    "pipeline_tag",
    "private",
    "safetensors",
    "siblings",
    "tags",
)

HUGGINGFACE_FALLBACK_TASKS: Final[tuple[str, ...]] = (
    "text-generation",
    "text-classification",
    "feature-extraction",
    "question-answering",
    "sentence-similarity",
    "token-classification",
    "summarization",
    "translation",
)

HUGGINGFACE_FALLBACK_LIBRARIES: Final[tuple[str, ...]] = (
    "transformers",
    "diffusers",
    "sentence-transformers",
    "gguf",
    "peft",
)
