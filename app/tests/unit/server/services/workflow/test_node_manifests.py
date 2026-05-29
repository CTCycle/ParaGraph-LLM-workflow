from __future__ import annotations

from server.services.workflow.node_handlers import NODE_HANDLERS
from server.services.workflow.nodes.registry import node_registry


def test_all_manifests_load() -> None:
    assert node_registry.list()


def test_no_duplicate_node_type_version() -> None:
    keys = [(manifest.id, manifest.version) for manifest in node_registry.list()]
    assert len(keys) == len(set(keys))


def test_every_manifest_executor_key_has_handler() -> None:
    missing = [
        manifest.runtime.executor_key
        for manifest in node_registry.list()
        if manifest.runtime.plugin is None
        and manifest.runtime.executor_key not in NODE_HANDLERS
    ]
    assert missing == []


def test_every_handler_referenced_by_manifest_is_callable() -> None:
    for manifest in node_registry.list():
        if manifest.runtime.plugin is not None:
            continue
        assert callable(NODE_HANDLERS[manifest.runtime.executor_key].executor)


def test_existing_node_manifests_remain_backward_compatible() -> None:
    prompt = node_registry.get("PROMPT_TEMPLATE", 1)
    assert prompt is not None
    assert prompt.runtime.executor_key == "prompt_template"
