from __future__ import annotations

from server.services.workflow.node_handlers.rag import (
    _context_builder_executor,
    _html_to_text_executor,
)

###############################################################################
def test_html_to_text_strips_script_style_nav() -> None:
    result = _html_to_text_executor(
        {}, {"html": "<script>x</script><nav>n</nav><p>Hello</p>"}
    )
    assert "x" not in result["result"]
    assert "n" not in result["result"]
    assert "Hello" in result["result"]

###############################################################################
def test_context_builder_respects_token_budget() -> None:
    result = _context_builder_executor(
        {"token_budget": 2}, {"chunks": [{"text": "one two three"}]}
    )
    assert result["result"] == "one two"

###############################################################################
def test_context_builder_accepts_manifest_inputs_and_coerces_malformed_values() -> None:
    result = _context_builder_executor(
        {"token_budget": 3},
        {"value": [None, {"content": "one two three"}, {"text": "four"}]},
    )
    assert result["result"] == "one two three"

    text_input_result = _context_builder_executor(
        {"token_budget": 1}, {"text": "four five"}
    )
    assert text_input_result["result"] == "four"

    empty_result = _context_builder_executor({}, {"value": None})
    assert empty_result["result"] == ""

###############################################################################
def test_html_to_text_coerces_none_and_recovers_malformed_markup() -> None:
    assert _html_to_text_executor({}, {"text": None})["result"] == ""
    assert (
        _html_to_text_executor({}, {"text": "<p>Readable <strong>text"})["result"]
        == "Readable text"
    )
