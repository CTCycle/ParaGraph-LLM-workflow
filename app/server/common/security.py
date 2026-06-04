from __future__ import annotations

from pathlib import Path
from typing import Any

from server.configurations.startup import get_configuration_runtime


_SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "authorization",
)


def is_cloud_deployment() -> bool:
    return (
        get_configuration_runtime()
        .environment()
        .get_bool("PARAGRAPH_CLOUD_MODE", False)
    )


def ensure_path_within_root(path: Path, root: Path, *, label: str) -> Path:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} must resolve inside {resolved_root}") from exc
    return resolved_path


def redact_sensitive_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if any(token in normalized_key for token in _SENSITIVE_KEY_TOKENS):
                redacted[key] = "***"
            else:
                redacted[key] = redact_sensitive_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_payload(item) for item in value)
    return value
