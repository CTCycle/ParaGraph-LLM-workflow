from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.services.workflow.nodes import node_registry
from server.services.workflow.templates import WorkflowTemplateService
from server.services.workflow import templates as templates_module


def _prompt_manifest_payload() -> dict[str, object]:
    manifest = node_registry.get("PROMPT", 1)
    assert manifest is not None
    return manifest.model_dump(mode="json")


def _write_template(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_template_service_rejects_missing_required_node_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(templates_module, "TEMPLATE_ROOT", tmp_path)
    service = WorkflowTemplateService()

    _write_template(
        tmp_path / "missing_node.json",
        {
            "id": "missing-node",
            "name": "Missing Node",
            "description": "Invalid template with missing required node manifest.",
            "tags": ["test"],
            "definition": {
                "schema_version": 2,
                "nodes": [],
                "connections": [],
                "metadata": {},
            },
            "visual_graph": {
                "schema_version": 2,
                "nodes": [],
                "groups": [],
                "comments": [],
            },
            "required_nodes": [
                {
                    "id": "MISSING_NODE",
                    "version": 1,
                    "name": "Missing",
                    "category": "processing",
                    "description": "Missing",
                    "inputs": [],
                    "outputs": [],
                    "parameters": [],
                    "ui": {
                        "default_width": 320,
                        "accent_color": "#4aa3ff",
                        "collapsed_by_default": False,
                    },
                    "runtime": {
                        "executor_key": "missing",
                        "cacheable": False,
                        "deterministic": True,
                        "side_effecting": False,
                    },
                }
            ],
            "metadata": {},
        },
    )

    with pytest.raises(ValueError, match="missing node manifests"):
        service.list_templates()


def test_template_service_rejects_non_compiling_definition(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(templates_module, "TEMPLATE_ROOT", tmp_path)
    service = WorkflowTemplateService()

    _write_template(
        tmp_path / "invalid_compile.json",
        {
            "id": "invalid-compile",
            "name": "Invalid Compile",
            "description": "Template that fails compiler checks.",
            "tags": ["test"],
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "text_output_1",
                        "node_type": "TEXT_OUTPUT",
                        "node_version": 1,
                        "parameters": {},
                    }
                ],
                "connections": [],
                "metadata": {},
            },
            "visual_graph": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "text_output_1",
                        "x": 50,
                        "y": 60,
                        "width": 280,
                        "height": 120,
                        "collapsed": False,
                    }
                ],
                "groups": [],
                "comments": [],
            },
            "required_nodes": [_prompt_manifest_payload()],
            "metadata": {},
        },
    )

    with pytest.raises(ValueError, match="failed compilation"):
        service.list_templates()

