from __future__ import annotations

import sys
from typing import TypeVar


T = TypeVar("T")

###############################################################################
def resolve_core_override(name: str, default: T) -> T:
    core_module = sys.modules.get("server.services.workflow.node_handlers.core")
    return getattr(core_module, name, default)


__all__ = ["resolve_core_override"]
