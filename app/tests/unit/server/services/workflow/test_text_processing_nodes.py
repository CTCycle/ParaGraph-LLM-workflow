from __future__ import annotations

from server.services.workflow.node_handlers.processing.text_processing import (
    _deduplicate_text_executor,
    _join_merge_text_executor,
    _regex_extract_executor,
    _token_counter_executor,
    _truncate_to_budget_executor,
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

###############################################################################
def test_token_counter_estimates_tokens_and_cost() -> None:
    result = _token_counter_executor({"cost_per_token": 0.1}, {"text": "a b"})
    assert result["result"]["tokens"] == 2

###############################################################################
def test_truncate_supports_first_last_and_balanced_modes() -> None:
    text = "one two three four"
    assert (
        _truncate_to_budget_executor({"max_tokens": 2}, {"text": text})["result"]
        == "one two"
    )
    assert (
        _truncate_to_budget_executor({"max_tokens": 2, "mode": "last"}, {"text": text})[
            "result"
        ]
        == "three four"
    )
