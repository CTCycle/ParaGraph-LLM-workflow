from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from server.domain.node_catalog import NodeManifest
from server.services.workflow.node_handlers import NODE_HANDLERS
from server.services.workflow.nodes.registry import node_registry

###############################################################################
def test_all_manifests_load() -> None:
    assert node_registry.list()

###############################################################################
def test_no_duplicate_node_type_version() -> None:
    keys = [(manifest.id, manifest.version) for manifest in node_registry.list()]
    assert len(keys) == len(set(keys))

###############################################################################
def test_every_manifest_executor_key_has_handler() -> None:
    missing = [
        manifest.runtime.executor_key
        for manifest in node_registry.list()
        if manifest.runtime.plugin is None
        and manifest.runtime.executor_key not in NODE_HANDLERS
    ]
    assert missing == []

###############################################################################
def test_every_handler_referenced_by_manifest_is_callable() -> None:
    for manifest in node_registry.list():
        if manifest.runtime.plugin is not None:
            continue
        assert callable(NODE_HANDLERS[manifest.runtime.executor_key].executor)

###############################################################################
def test_every_registered_handler_is_referenced_by_a_manifest() -> None:
    referenced = {
        manifest.runtime.executor_key
        for manifest in node_registry.list()
        if manifest.runtime.plugin is None
    }
    assert set(NODE_HANDLERS).difference(referenced) == set()

###############################################################################
def test_every_manifest_parameter_model_accepts_manifest_defaults() -> None:
    required_parameter_fixtures: dict[str, dict[str, object]] = {
        "CRUD_CREATE": {"table": "items"},
        "CRUD_DELETE": {"table": "items"},
        "CRUD_READ": {"table": "items"},
        "CRUD_UPDATE": {"table": "items"},
        "CRUD_UPSERT": {
            "table": "items",
            "conflict_columns": "id",
            "insert_values": {"id": 1},
            "update_values": {"id": 1},
        },
        "LOAD_DOCUMENTS": {"folder_path": "."},
        "LOAD_TEXT": {"storage_path": "input.txt"},
        "PROMPT_TEMPLATE": {"template": "{{ text }}"},
        "SQL_DATABASE": {"db_name": "paragraph"},
        "SQL_FILE_DATABASE": {"db_path": "database.db"},
        "VECTOR_STORE": {"storage_path": "vectorstores"},
    }
    for manifest in node_registry.list():
        if manifest.runtime.plugin is not None:
            continue
        handler = NODE_HANDLERS[manifest.runtime.executor_key]
        if handler.parameter_model is None:
            continue
        defaults = {
            parameter.name: parameter.default
            for parameter in manifest.parameters
            if parameter.default is not None
        }
        defaults.update(required_parameter_fixtures.get(manifest.id, {}))
        try:
            handler.parameter_model.model_validate(defaults)
        except ValidationError as exc:
            pytest.fail(
                f"{manifest.id} v{manifest.version} defaults do not satisfy "
                f"{handler.parameter_model.__name__}: {exc}"
            )

###############################################################################
@pytest.mark.parametrize("field", ["inputs", "outputs", "controllers", "parameters"])
def test_manifest_rejects_duplicate_contract_names(field: str) -> None:
    definition = {
        "name": "duplicate",
        "data_type": "TEXT",
    }
    payload = {
        "id": "DUPLICATE_CONTRACT_TEST",
        "name": "Duplicate contract test",
        "category": "processing",
        "description": "Test fixture",
        field: [definition, definition],
        "runtime": {"executor_key": "normalize_text"},
    }

    with pytest.raises(ValidationError, match=f"duplicate {field[:-1]}"):
        NodeManifest.model_validate(payload)

###############################################################################
def test_execute_rejects_undeclared_handler_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = node_registry.get("PROMPT", 1)
    assert manifest is not None
    executor_key = manifest.runtime.executor_key
    handler = NODE_HANDLERS[executor_key]
    monkeypatch.setitem(
        NODE_HANDLERS,
        executor_key,
        replace(
            handler,
            executor=lambda _parameters, _inputs: {
                "text": "ok",
                "surprise": True,
            },
        ),
    )

    with pytest.raises(ValueError, match="produced undeclared outputs: surprise"):
        node_registry.execute("PROMPT", 1, {"text": "ok"}, {})
