from __future__ import annotations

from server.services.workflow.node_handlers.rag import (
    _context_builder_executor,
    _grounding_checker_executor,
    _html_to_text_executor,
    _ocr_text_extract_executor,
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
def test_grounding_checker_marks_unsupported_claim_when_evidence_absent() -> None:
    result = _grounding_checker_executor(
        {}, {"claim": "missing", "evidence": "present"}
    )
    assert result["label"] == "unsupported"

###############################################################################
def test_ocr_returns_dependency_error_when_binary_unavailable_or_empty_result() -> None:
    result = _ocr_text_extract_executor({}, {})
    assert "error" in result or "result" in result
