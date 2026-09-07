from __future__ import annotations

from server.services.workflow.node_handlers.processing.text_processing import (
    _deduplicate_text_executor,
    _join_merge_text_executor,
    _regex_extract_executor,
)

###############################################################################
def test_regex_extract_returns_named_groups_and_matches() -> None:
    result = _regex_extract_executor({"pattern": r"(?P<word>\w+)"}, {"text": "alpha"})
    assert result["result"][0]["groups"] == {"word": "alpha"}

###############################################################################
def test_join_merge_handles_list_and_scalar_inputs() -> None:
    assert (
        _join_merge_text_executor({"separator": ","}, {"items": ["a", "b"]})["result"]
        == "a,b"
    )

###############################################################################
def test_deduplicate_removes_repeated_boilerplate() -> None:
    assert _deduplicate_text_executor({}, {"text": "A\nA\nB"})["result"] == "A\nB"
