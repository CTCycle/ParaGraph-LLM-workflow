from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from pydantic import BaseModel


Executor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
PortValidator = Callable[[Any], Any]


###############################################################################
@dataclass(frozen=True)
class NodeHandler:
    executor: Executor
    parameter_model: type[BaseModel] | None = None
    input_validators: Mapping[str, PortValidator] = field(default_factory=dict)
    output_validators: Mapping[str, PortValidator] = field(default_factory=dict)
