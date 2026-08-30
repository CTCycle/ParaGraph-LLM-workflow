from __future__ import annotations

from typing import Any

from sqlalchemy.types import JSON, TypeDecorator


###############################################################################
class JSONSequence(TypeDecorator):
    impl = JSON
    cache_ok = True

    # -------------------------------------------------------------------------
    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return value

    # -------------------------------------------------------------------------
    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value
