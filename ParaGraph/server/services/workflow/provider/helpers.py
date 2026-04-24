from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from ParaGraph.server.domain.provider import ModelMetadata, ProviderMetadata
from ParaGraph.server.services.workflow.provider.constants import HUGGINGFACE_REPO_ID_PATTERN
from ParaGraph.server.services.workflow.provider.errors import ProviderApiError

###############################################################################
def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return int(float(text))
            except ValueError:
                return None
    return None

###############################################################################
def _coerce_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

###############################################################################
def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None

###############################################################################
def _normalize_ollama_library_slug(href: str) -> str | None:
    if not href.startswith("/library/"):
        return None
    raw = href[len("/library/") :].strip()
    if not raw:
        return None
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    segment = raw.split("/", 1)[0].strip()
    if not segment:
        return None
    slug = unquote(segment).strip().lower()
    if not slug or slug in {"library", "search"}:
        return None
    return slug

###############################################################################
def _model_basename(model: str) -> str:
    return model.split(":", 1)[0].strip().lower()

###############################################################################
def _normalize_huggingface_repo_id(repo_id: str) -> str:
    normalized = repo_id.strip().strip("/")
    if not normalized or not HUGGINGFACE_REPO_ID_PATTERN.fullmatch(normalized):
        raise ProviderApiError(
            "Invalid Hugging Face repository id. Use the format 'namespace/model'.",
            status_code=400,
        )
    return normalized

###############################################################################
def _huggingface_model_dir_name(repo_id: str) -> str:
    return repo_id.replace("/", "--")

###############################################################################
def _huggingface_repo_id_from_dir_name(value: str) -> str | None:
    if "--" not in value:
        return None
    candidate = value.replace("--", "/")
    if not HUGGINGFACE_REPO_ID_PATTERN.fullmatch(candidate):
        return None
    return candidate

###############################################################################
def _resolve_visibility(private: bool | None, gated: bool | None) -> str:
    if gated is True:
        return "gated"
    if private is True:
        return "private"
    if private is False:
        return "public"
    return "unknown"

###############################################################################
def _extract_huggingface_model_size(payload: Any) -> int | None:
    for key in ("size", "model_size", "total_size", "usedStorage"):
        candidate = _safe_int(_payload_value(payload, key))
        if candidate is not None and candidate >= 0:
            return candidate

    safetensors = _payload_value(payload, "safetensors")
    if isinstance(safetensors, dict):
        total = _safe_int(
            safetensors.get("total")
            or safetensors.get("total_size")
            or safetensors.get("size")
        )
        if total is not None and total >= 0:
            return total

    siblings = _payload_value(payload, "siblings")
    if isinstance(siblings, list) and siblings:
        total_bytes = 0
        found_size = False
        for sibling in siblings:
            if isinstance(sibling, dict):
                size_value = _safe_int(sibling.get("size"))
            else:
                size_value = _safe_int(getattr(sibling, "size", None))
            if size_value is None or size_value < 0:
                continue
            found_size = True
            total_bytes += size_value
        if found_size:
            return total_bytes

    return None

###############################################################################
def _extract_huggingface_tag_values(payload: Any) -> tuple[str, ...]:
    values: set[str] = set()

    if isinstance(payload, dict):
        iterable = list(payload.values())
    elif isinstance(payload, list):
        iterable = payload
    else:
        iterable = []

    for item in iterable:
        candidate: str | None = None
        if isinstance(item, str):
            candidate = _coerce_optional_text(item)
        elif isinstance(item, dict):
            for key in ("id", "label", "name", "value"):
                candidate = _coerce_optional_text(item.get(key))
                if candidate:
                    break
        else:
            for attribute in ("id", "label", "name", "value"):
                candidate = _coerce_optional_text(getattr(item, attribute, None))
                if candidate:
                    break

        if candidate:
            values.add(candidate)

    return tuple(sorted(values))

###############################################################################
def _payload_value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return getattr(payload, key, None)

###############################################################################
PROVIDER_CAPABILITIES = {
    "ollama": ProviderMetadata(
        name="ollama",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
    ),
    "openai": ProviderMetadata(
        name="openai",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "gemini": ProviderMetadata(
        name="gemini",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "claude": ProviderMetadata(
        name="claude",
        supports_chat=True,
        supports_embeddings=False,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "huggingface": ProviderMetadata(
        name="huggingface",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=False,
        supports_tool_calling=False,
    ),
}

###############################################################################
CURATED_MODELS: dict[str, tuple[ModelMetadata, ...]] = {
    "ollama": (
        ModelMetadata(
            provider="ollama",
            model="nomic-embed-text",
            label="nomic-embed-text",
            supports_embeddings=True,
        ),
        ModelMetadata(
            provider="ollama",
            model="mxbai-embed-large",
            label="mxbai-embed-large",
            supports_embeddings=True,
        ),
        ModelMetadata(
            provider="ollama", model="bge-m3", label="bge-m3", supports_embeddings=True
        ),
    ),
    "openai": (
        ModelMetadata(
            provider="openai",
            model="gpt-5.4",
            label="GPT-5.4",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="openai",
            model="gpt-5-mini",
            label="GPT-5 mini",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="openai",
            model="gpt-5-nano",
            label="GPT-5 nano",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="openai", model="gpt-4.1", label="GPT-4.1", supports_image=True
        ),
        ModelMetadata(
            provider="openai",
            model="text-embedding-3-small",
            label="Text Embedding 3 Small",
            supports_embeddings=True,
        ),
        ModelMetadata(
            provider="openai",
            model="text-embedding-3-large",
            label="Text Embedding 3 Large",
            supports_embeddings=True,
        ),
    ),
    "gemini": (
        ModelMetadata(
            provider="gemini",
            model="gemini-3-pro-preview",
            label="Gemini 3 Pro Preview",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="gemini",
            model="gemini-3-flash-preview",
            label="Gemini 3 Flash Preview",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="gemini",
            model="gemini-2.5-pro",
            label="Gemini 2.5 Pro",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="gemini",
            model="gemini-2.5-flash",
            label="Gemini 2.5 Flash",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="gemini",
            model="gemini-2.5-flash-lite",
            label="Gemini 2.5 Flash-Lite",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="gemini",
            model="gemini-embedding-001",
            label="Gemini Embedding 001",
            supports_embeddings=True,
        ),
    ),
    "claude": (
        ModelMetadata(
            provider="claude",
            model="claude-opus-4-1-20250805",
            label="Claude Opus 4.1",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="claude",
            model="claude-sonnet-4-20250514",
            label="Claude Sonnet 4",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="claude",
            model="claude-3-7-sonnet-latest",
            label="Claude Sonnet 3.7",
            supports_image=True,
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="claude",
            model="claude-3-5-haiku-latest",
            label="Claude Haiku 3.5",
            supports_image=True,
        ),
    ),
    "huggingface": (
        ModelMetadata(
            provider="huggingface",
            model="meta-llama/Llama-3.2-3B-Instruct",
            label="Llama 3.2 3B Instruct",
        ),
        ModelMetadata(
            provider="huggingface",
            model="Qwen/Qwen2.5-7B-Instruct",
            label="Qwen 2.5 7B Instruct",
        ),
        ModelMetadata(
            provider="huggingface",
            model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            label="DeepSeek R1 Distill Qwen 7B",
            supports_reasoning=True,
        ),
        ModelMetadata(
            provider="huggingface",
            model="sentence-transformers/all-MiniLM-L6-v2",
            label="all-MiniLM-L6-v2",
            supports_embeddings=True,
        ),
        ModelMetadata(
            provider="huggingface",
            model="intfloat/e5-base-v2",
            label="E5 Base v2",
            supports_embeddings=True,
        ),
        ModelMetadata(
            provider="huggingface",
            model="BAAI/bge-small-en-v1.5",
            label="BGE Small EN v1.5",
            supports_embeddings=True,
        ),
    ),
}

###############################################################################
def _normalize_provider(provider: str) -> str:
    return provider.lower().strip()

###############################################################################
def _infer_ollama_metadata(model_name: str) -> ModelMetadata:
    normalized = model_name.lower()
    supports_image = any(
        token in normalized for token in ("llava", "vision", "bakllava", "moondream")
    )
    supports_reasoning = any(
        token in normalized for token in ("deepseek-r1", "qwq", "reason", "qwen3")
    )
    return ModelMetadata(
        provider="ollama",
        model=model_name,
        label=model_name,
        supports_image=supports_image,
        supports_reasoning=supports_reasoning,
        supports_structured_output=True,
    )


def _infer_huggingface_metadata(repo_id: str) -> ModelMetadata:
    normalized = repo_id.lower()
    supports_image = any(
        token in normalized
        for token in ("vision", "vl", "llava", "pixtral", "moondream")
    )
    supports_reasoning = any(
        token in normalized for token in ("reason", "r1", "r2", "qwq", "o1", "o3")
    )
    return ModelMetadata(
        provider="huggingface",
        model=repo_id,
        label=repo_id,
        supports_image=supports_image,
        supports_reasoning=supports_reasoning,
        supports_structured_output=True,
    )

