from __future__ import annotations

from pydantic import BaseModel


###############################################################################
class RagParameters(BaseModel):
    token_budget: int = 1200
    include_metadata: bool = True
