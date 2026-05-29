from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdvancedTextParameters(BaseModel):
    patterns: list[str] = Field(default_factory=list)
    threshold: float = 0.85
    replacement: str = "[REDACTED]"
    metadata: dict[str, Any] = Field(default_factory=dict)
