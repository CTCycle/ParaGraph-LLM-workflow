from __future__ import annotations

from server.contracts.node_handler_processing import (
    ByDelimiterChunksParameters,
    ByStructureChunksParameters,
    FixedSizeChunksParameters,
    MergeSmallChunksParameters,
    RecursiveSplitChunksParameters,
    RegexSplitChunksParameters,
    SentenceWindowChunksParameters,
)
from server.services.workflow.nodes.handler import NodeHandler
from server.services.workflow.node_handlers.processing.delimiter import (
    _by_delimiter_chunks_executor,
)
from server.services.workflow.node_handlers.processing.fixed import (
    _fixed_size_chunks_executor,
)
from server.services.workflow.node_handlers.processing.merge import (
    _merge_small_chunks_executor,
)
from server.services.workflow.node_handlers.processing.recursive import (
    _recursive_split_chunks_executor,
)
from server.services.workflow.node_handlers.processing.sentence import (
    _sentence_window_chunks_executor,
)
from server.services.workflow.node_handlers.processing.structure import (
    _by_structure_chunks_executor,
    _regex_split_chunks_executor,
)
from server.services.workflow.node_handlers.processing.text_processing import (
    TEXT_PROCESSING_HANDLERS,
)


PROCESSING_HANDLERS = {
    "fixed_size_chunks": NodeHandler(
        executor=_fixed_size_chunks_executor, parameter_model=FixedSizeChunksParameters
    ),
    "by_delimiter_chunks": NodeHandler(
        executor=_by_delimiter_chunks_executor,
        parameter_model=ByDelimiterChunksParameters,
    ),
    "by_structure_chunks": NodeHandler(
        executor=_by_structure_chunks_executor,
        parameter_model=ByStructureChunksParameters,
    ),
    "regex_split_chunks": NodeHandler(
        executor=_regex_split_chunks_executor,
        parameter_model=RegexSplitChunksParameters,
    ),
    "recursive_split_chunks": NodeHandler(
        executor=_recursive_split_chunks_executor,
        parameter_model=RecursiveSplitChunksParameters,
    ),
    "sentence_window_chunks": NodeHandler(
        executor=_sentence_window_chunks_executor,
        parameter_model=SentenceWindowChunksParameters,
    ),
    "merge_small_chunks": NodeHandler(
        executor=_merge_small_chunks_executor,
        parameter_model=MergeSmallChunksParameters,
    ),
    **TEXT_PROCESSING_HANDLERS,
}

__all__ = ["PROCESSING_HANDLERS"]
