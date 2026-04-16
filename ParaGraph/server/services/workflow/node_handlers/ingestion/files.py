from __future__ import annotations

from ParaGraph.server.services.workflow.node_handlers.ingestion import (
    _load_file_text,
    _resolve_local_path,
)


def load_file_text(*args, **kwargs):
    return _load_file_text(*args, **kwargs)


def resolve_local_path(*args, **kwargs):
    return _resolve_local_path(*args, **kwargs)
