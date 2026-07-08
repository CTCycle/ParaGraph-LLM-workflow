from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

###############################################################################
class HttpBaseParameters(BaseModel):
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 30.0

###############################################################################
class HttpBodyParameters(HttpBaseParameters):
    json_body: Any = None

###############################################################################
class HttpGetParameters(HttpBaseParameters):
    pass

###############################################################################
class HttpPostParameters(HttpBodyParameters):
    pass

###############################################################################
class HttpPutParameters(HttpBodyParameters):
    pass

###############################################################################
class HttpPatchParameters(HttpBodyParameters):
    pass

###############################################################################
class HttpDeleteParameters(HttpBaseParameters):
    pass
