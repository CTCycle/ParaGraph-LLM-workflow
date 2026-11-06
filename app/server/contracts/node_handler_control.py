from __future__ import annotations

from pydantic import BaseModel


###############################################################################
class ControlParameters(BaseModel):
    keyword: str = ""
    regex: bool = False
    operation: str = "identity"
