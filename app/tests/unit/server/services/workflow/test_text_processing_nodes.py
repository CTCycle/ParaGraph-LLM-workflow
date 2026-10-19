from __future__ import annotations

from server.services.workflow.node_handlers.processing.text_processing import (
    _deduplicate_text_executor,
    _join_merge_text_executor,
    _regex_extract_executor,
    _regex_replace_executor,
    _normalize_text_executor,
)

###############################################################################
def test_regex_extract_returns_named_groups_and_matches() -> None:
    result = _regex_extract_executor({"pattern": r"(?P<word>\w+)"}, {"text": "alpha"})
    assert result["result"][0]["groups"] == {"word": "alpha"}

###############################################################################
def test_normalize_text_applies_unicode_and_whitespace_normalization() -> None:
    result = _normalize_text_executor(
        {"collapse_whitespace": True}, {"text": "Ａlpha　 “target”"}
    )
    assert result["result"] == 'Alpha "target"'

###############################################################################
def test_regex_replace_replaces_matching_text() -> None:
    result = _regex_replace_executor(
        {"pattern": r"target-\d+", "replacement": "item"},
        {"text": "Selected target-42"},
    )
    assert result["result"] == "Selected item"

###############################################################################
def test_join_merge_handles_list_and_scalar_inputs() -> None:
    assert (
        _join_merge_text_executor({"separator": ","}, {"items": ["a", "b"]})["result"]
        == "a,b"
    )

###############################################################################
def test_deduplicate_removes_repeated_boilerplate() -> None:
    assert _deduplicate_text_executor({}, {"text": "A\nA\nB"})["result"] == "A\nB"
