from __future__ import annotations

import pytest

from ParaGraph.server.services.workflow import node_registry


def test_prompt_template_replaces_single_brace_variables() -> None:
    payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {'template': 'Hello {name} from {city}.'},
        {
            'variables': [
                {'name': 'Alice'},
                {'city': 'Rome'},
            ]
        },
    )

    assert payload['text'] == 'Hello Alice from Rome.'


def test_prompt_template_fails_when_placeholder_is_missing() -> None:
    with pytest.raises(ValueError, match='missing variable values'):
        node_registry.execute('PROMPT_TEMPLATE', 1, {'template': 'A={known} B={missing}'}, {'variables': {'known': 'ok'}})


def test_prompt_template_fails_when_duplicate_variable_is_connected() -> None:
    with pytest.raises(ValueError, match='duplicate variable key'):
        node_registry.execute(
            'PROMPT_TEMPLATE',
            1,
            {'template': 'Name={name}'},
            {'variables': [{'name': 'Alice'}, {'name': 'Bob'}]},
        )


def test_prompt_template_merges_multiple_input_maps() -> None:
    payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {'template': '{first} {second} {third}'},
        {'variables': [{'first': 'A'}, {'second': 'B', 'third': 'C'}]},
    )

    assert payload['text'] == 'A B C'


def test_assign_name_emits_exact_text_value_under_configured_key() -> None:
    payload = node_registry.execute(
        'ASSIGN_NAME',
        1,
        {'name': 'name'},
        {'value': 'Ada'},
    )

    assert payload == {'variable': {'name': 'Ada'}}


def test_assign_name_emits_exact_structured_value_under_configured_key() -> None:
    input_value = {
        'document': {'id': 'doc-1', 'tags': ['alpha', 'beta']},
        'score': 0.91,
        'enabled': True,
    }
    payload = node_registry.execute(
        'ASSIGN_NAME',
        1,
        {'name': 'payload'},
        {'value': input_value},
    )

    assert payload == {'variable': {'payload': input_value}}
