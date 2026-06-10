from __future__ import annotations

import pytest

from server.services.workflow import node_registry


###############################################################################
def test_prompt_template_replaces_single_brace_variables() -> None:
    payload = node_registry.execute(
        "PROMPT_TEMPLATE",
        1,
        {"template": "Hello {name} from {city}."},
        {
            "variables": [
                {"name": "Alice"},
                {"city": "Rome"},
            ]
        },
    )

    assert payload["text"] == "Hello Alice from Rome."


###############################################################################
def test_prompt_template_fails_when_placeholder_is_missing() -> None:
    with pytest.raises(ValueError, match="missing variable values"):
        node_registry.execute(
            "PROMPT_TEMPLATE",
            1,
            {"template": "A={known} B={missing}"},
            {"variables": {"known": "ok"}},
        )


###############################################################################
def test_prompt_template_fails_when_duplicate_variable_is_connected() -> None:
    with pytest.raises(ValueError, match="duplicate variable key"):
        node_registry.execute(
            "PROMPT_TEMPLATE",
            1,
            {"template": "Name={name}"},
            {"variables": [{"name": "Alice"}, {"name": "Bob"}]},
        )


###############################################################################
def test_prompt_template_merges_multiple_input_maps() -> None:
    payload = node_registry.execute(
        "PROMPT_TEMPLATE",
        1,
        {"template": "{first} {second} {third}"},
        {"variables": [{"first": "A"}, {"second": "B", "third": "C"}]},
    )

    assert payload["text"] == "A B C"
