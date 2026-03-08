from __future__ import annotations

from typing import Any


# -----------------------------------------------------------------------------
def coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


# -----------------------------------------------------------------------------
def coerce_int(
    value: Any, default: int, minimum: int | None = None, maximum: int | None = None
) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = default
    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum
    return candidate


# -----------------------------------------------------------------------------
def coerce_float(
    value: Any,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        candidate = default
    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum
    return candidate


# -----------------------------------------------------------------------------
def coerce_str_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
