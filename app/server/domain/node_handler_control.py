from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


###############################################################################
class ControlParameters(BaseModel):
    label: str = ""
    keyword: str = ""
    operation: str = "identity"
    metadata: dict[str, Any] = Field(default_factory=dict)
