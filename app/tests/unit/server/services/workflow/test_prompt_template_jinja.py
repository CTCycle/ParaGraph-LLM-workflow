from __future__ import annotations

import pytest

from server.services.workflow.node_handlers.core.prompts import (
    _prompt_template_executor,
)


###############################################################################
def test_render_summary_from_upstream_json_object() -> None:
    result = _prompt_template_executor(
        {"template": "{{ summary }}"},
        {"variables": {"summary": "Done"}},
    )
    assert result["text"] == "Done"


###############################################################################
def test_render_list_variable_with_join_filter() -> None:
    result = _prompt_template_executor(
        {"template": "{{ keywords | join(', ') }}"},
        {"variables": {"keywords": ["alpha", "beta"]}},
    )
    assert result["text"] == "alpha, beta"


###############################################################################
def test_render_system_and_user_sections() -> None:
    result = _prompt_template_executor(
        {
            "system_template": "System {{ role }}",
            "user_template": "User {{ task }}",
        },
        {"variables": {"role": "R", "task": "T"}},
    )
    assert result["system"] == "System R"
    assert result["user"] == "User T"


###############################################################################
def test_strict_missing_variable_raises_clear_validation_error() -> None:
    with pytest.raises(ValueError, match="failed to render Jinja template"):
        _prompt_template_executor({"template": "{{ missing }}"}, {"variables": {}})


###############################################################################
def test_legacy_format_syntax_is_not_interpolated() -> None:
    result = _prompt_template_executor(
        {"template": "Hello {name}"},
        {"variables": {"name": "World"}},
    )
    assert result["text"] == "Hello {name}"
