from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.services.workflow.nodes import registry as node_module

###############################################################################
def write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

###############################################################################
def build_plugin_manifest(script_path: str) -> dict[str, object]:
    return {
        "id": "CUSTOM_SCRIPT_NODE",
        "version": 1,
        "name": "Custom Script Node",
        "category": "processing",
        "description": "Execute custom logic from a local plugin script.",
        "inputs": [
            {
                "name": "text",
                "data_type": "TEXT",
                "required": True,
                "accepts_multiple": False,
            }
        ],
        "outputs": [
            {
                "name": "result",
                "data_type": "TEXT",
                "required": True,
                "accepts_multiple": False,
            }
        ],
        "parameters": [
            {
                "name": "prefix",
                "data_type": "TEXT",
                "default": "",
                "constraints": {},
                "ui_control": "text",
                "description": "String prefix.",
            }
        ],
        "ui": {
            "default_width": 280,
            "accent_color": "#4aa3ff",
            "icon": "sparkles",
            "collapsed_by_default": False,
        },
        "runtime": {
            "executor_key": "custom.plugin",
            "cacheable": False,
            "deterministic": True,
            "side_effecting": False,
            "plugin": {
                "script_path": script_path,
                "entrypoint": "execute",
            },
        },
    }

###############################################################################
def test_plugin_node_executes_script_runtime(monkeypatch, tmp_path: Path) -> None:
    node_root = tmp_path / "nodes"
    plugins_root = node_root / "plugins"
    plugins_root.mkdir(parents=True, exist_ok=True)

    plugin_script = plugins_root / "custom_script_node.py"
    plugin_script.write_text(
        """
def execute(parameters, inputs):
    prefix = str(parameters.get('prefix', ''))
    text = str(inputs.get('text', ''))
    return {'result': f"{prefix}{text}".upper()}
""".strip(),
        encoding="utf-8",
    )

    write_manifest(
        node_root / "custom_script_node_v1.json",
        build_plugin_manifest("plugins/custom_script_node.py"),
    )

    monkeypatch.setattr(node_module, "NODE_ROOT", node_root)
    registry = node_module.NodeRegistry()

    result = registry.execute(
        "CUSTOM_SCRIPT_NODE", 1, {"prefix": "pre-"}, {"text": "hello"}
    )
    assert result == {"result": "PRE-HELLO"}

###############################################################################
def test_plugin_node_rejects_absolute_script_paths(monkeypatch, tmp_path: Path) -> None:
    node_root = tmp_path / "nodes"
    node_root.mkdir(parents=True, exist_ok=True)
    absolute_script = (tmp_path / "absolute_plugin.py").resolve()

    write_manifest(
        node_root / "custom_script_node_v1.json",
        build_plugin_manifest(str(absolute_script)),
    )

    monkeypatch.setattr(node_module, "NODE_ROOT", node_root)
    with pytest.raises(ValueError, match="must be relative"):
        node_module.NodeRegistry()
