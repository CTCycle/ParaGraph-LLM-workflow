from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from server.services.workflow.provider.constants import HUGGINGFACE_REPO_ID_PATTERN
from server.services.workflow.provider.errors import ProviderApiError


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
