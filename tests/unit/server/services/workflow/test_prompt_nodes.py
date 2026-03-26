from __future__ import annotations

import pytest

from ParaGraph.server.services.workflow import node_registry


def test_prompt_template_substitutes_alias_and_raw_var_names() -> None:
    payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {
            'template': 'Hello {{name}} from {{var_2}}.',
            'variable_names': ['name'],
            'missing_variable': 'error',
            'cleanup': 'none',
        },
        {
            'var_1': 'Alice',
            'var_2': 'Rome',
        },
    )

    assert payload['text'] == 'Hello Alice from Rome.'


def test_prompt_template_supports_missing_variable_modes() -> None:
    with pytest.raises(ValueError, match='missing variable values'):
        node_registry.execute(
            'PROMPT_TEMPLATE',
            1,
            {
                'template': 'A={{known}} B={{missing}}',
                'variable_names': ['known'],
                'missing_variable': 'error',
                'cleanup': 'none',
            },
            {'var_1': 'ok'},
        )

    empty_payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {
            'template': 'A={{known}} B={{missing}}',
            'variable_names': ['known'],
            'missing_variable': 'empty',
            'cleanup': 'none',
        },
        {'var_1': 'ok'},
    )
    keep_payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {
            'template': 'A={{known}} B={{missing}}',
            'variable_names': ['known'],
            'missing_variable': 'keep_placeholder',
            'cleanup': 'none',
        },
        {'var_1': 'ok'},
    )

    assert empty_payload['text'] == 'A=ok B='
    assert keep_payload['text'] == 'A=ok B={{missing}}'


def test_prompt_template_cleanup_modes_apply_expected_formatting() -> None:
    payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {
            'template': '  {{var_1}}\n\n\n  {{var_2}}  ',
            'variable_names': [],
            'missing_variable': 'error',
            'cleanup': 'collapse_blank_lines',
        },
        {
            'var_1': 'First',
            'var_2': 'Second',
        },
    )

    assert payload['text'] == '  First\n\n  Second'


def test_prompt_template_coerces_chunk_document_and_json_inputs() -> None:
    payload = node_registry.execute(
        'PROMPT_TEMPLATE',
        1,
        {
            'template': '{{ctx}}\n---\n{{docs}}\n---\n{{obj}}',
            'variable_names': ['ctx', 'docs', 'obj'],
            'missing_variable': 'error',
            'cleanup': 'none',
        },
        {
            'var_1': [
                {
                    'id': 'chunk-1',
                    'document_id': 'doc-1',
                    'text': 'chunk text',
                    'source_uri': 'memory://doc-1',
                    'chunk_index': 0,
                    'token_count': 2,
                    'metadata': {},
                }
            ],
            'var_2': [
                {
                    'id': 'doc-1',
                    'text': 'document text',
                    'source_uri': 'memory://doc-1',
                    'mime_type': 'text/plain',
                    'metadata': {},
                }
            ],
            'var_3': {'alpha': 1},
        },
    )

    assert 'chunk text' in payload['text']
    assert 'document text' in payload['text']
    assert '"alpha": 1' in payload['text']
