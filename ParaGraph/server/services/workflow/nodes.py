from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.services.configuration import configuration_service
from ParaGraph.server.services.workflow.node_handlers import NODE_HANDLERS
from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.payloads import validate_data_type
from ParaGraph.server.services.workflow.provider import provider_service


NODE_ROOT = Path(RESOURCES_PATH) / "nodes"
ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"
MODEL_NODE_IDS = {"LLM_CHAT", "LLM_STRUCTURED"}
STRUCTURED_NODE_IDS = {"LLM_STRUCTURED"}


class NodeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], NodeManifest] = {}
        NODE_ROOT.mkdir(parents=True, exist_ok=True)
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        self.reload()

    def reload(self) -> None:
        definitions: dict[tuple[str, int], NodeManifest] = {}
        for path in sorted(NODE_ROOT.glob("*.json")):
            manifest = NodeManifest.model_validate_json(path.read_text(encoding="utf-8"))
            key = (manifest.id, manifest.version)
            if key in definitions:
                raise ValueError(f"Duplicate node manifest detected for {manifest.id} v{manifest.version}")
            self._assert_executor_known(manifest)
            definitions[key] = manifest
        self._definitions = definitions

    def _assert_executor_known(self, manifest: NodeManifest) -> None:
        if manifest.runtime.executor_key not in NODE_HANDLERS:
            raise ValueError(f"Unknown executor_key '{manifest.runtime.executor_key}' for node '{manifest.id}'")

    def _handler_for_manifest(self, manifest: NodeManifest) -> NodeHandler:
        return NODE_HANDLERS[manifest.runtime.executor_key]

    def get(self, node_type: str, version: int | None = None) -> NodeManifest | None:
        if version is not None:
            return self._definitions.get((node_type, version))
        matching = [manifest for (manifest_id, _), manifest in self._definitions.items() if manifest_id == node_type]
        if not matching:
            return None
        return sorted(matching, key=lambda item: item.version)[-1]

    def list(self) -> list[NodeManifest]:
        return sorted(self._definitions.values(), key=lambda item: (item.category, item.name, item.version))

    def catalog_response(self) -> NodeCatalogResponse:
        return NodeCatalogResponse(nodes=self.list())

    def import_manifest(self, manifest: NodeManifest) -> NodeManifest:
        self._assert_executor_known(manifest)
        if self.get(manifest.id, manifest.version) is not None:
            raise ValueError(f"Node manifest already exists for {manifest.id} v{manifest.version}")

        filename = f"{manifest.id.lower()}_v{manifest.version}.json"
        path = NODE_ROOT / filename
        path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")

        try:
            self.reload()
            created = self.get(manifest.id, manifest.version)
            if created is None:
                raise ValueError(f"Imported node manifest could not be reloaded: {manifest.id} v{manifest.version}")
            configuration_service.save_node_manifest(created)
        except Exception as exc:
            if path.exists():
                path.unlink()
            self.reload()
            raise ValueError(f"Failed to persist imported node manifest in database: {exc}") from exc

        return created

    def validate_parameters(self, node_type: str, node_version: int, parameters: dict[str, Any]) -> dict[str, Any]:
        manifest = self.get(node_type, node_version)
        if manifest is None:
            raise ValueError(f"Unknown node type/version '{node_type}' v{node_version}")
        handler = self._handler_for_manifest(manifest)
        payload = dict(parameters)
        if handler.parameter_model is not None:
            payload = handler.parameter_model.model_validate(payload).model_dump(mode="json")
        self._validate_parameter_constraints(manifest, payload)
        return payload

    def _validate_parameter_constraints(self, manifest: NodeManifest, parameters: dict[str, Any]) -> None:
        for parameter in manifest.parameters:
            if parameter.name not in parameters:
                continue
            value = parameters[parameter.name]
            constraints = parameter.constraints or {}
            if parameter.ui_control == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
                minimum = constraints.get("min")
                maximum = constraints.get("max")
                if minimum is not None and value < minimum:
                    raise ValueError(f"Parameter '{parameter.name}' must be greater than or equal to {minimum}")
                if maximum is not None and value > maximum:
                    raise ValueError(f"Parameter '{parameter.name}' must be less than or equal to {maximum}")
            options = constraints.get("options")
            if isinstance(options, list) and options and value not in options:
                raise ValueError(f"Parameter '{parameter.name}' must be one of: {', '.join(str(item) for item in options)}")

    def _validate_ports(self, manifest: NodeManifest, values: dict[str, Any], *, label: str) -> dict[str, Any]:
        ports = manifest.inputs if label == "input" else manifest.outputs
        validated = dict(values)
        for port in ports:
            if port.name not in values:
                if port.required and label == "output":
                    raise ValueError(f"Node '{manifest.id}' did not produce required output '{port.name}'")
                continue
            value = values[port.name]
            if value is None and not port.required:
                continue
            if port.accepts_multiple and isinstance(value, list):
                validated[port.name] = [validate_data_type(port.data_type, item) for item in value]
            else:
                validated[port.name] = validate_data_type(port.data_type, value)
        return validated

    def execute(self, node_type: str, node_version: int, parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        manifest = self.get(node_type, node_version)
        if manifest is None:
            raise ValueError(f"Unknown node type/version '{node_type}' v{node_version}")
        handler = self._handler_for_manifest(manifest)
        validated_parameters = self.validate_parameters(node_type, node_version, parameters)
        validated_inputs = self._validate_ports(manifest, inputs, label="input")
        for port_name, validator in handler.input_validators.items():
            if port_name in validated_inputs:
                validated_inputs[port_name] = validator(validated_inputs[port_name])
        outputs = handler.executor(validated_parameters, validated_inputs)
        validated_outputs = self._validate_ports(manifest, outputs, label="output")
        for port_name, validator in handler.output_validators.items():
            if port_name in validated_outputs:
                validated_outputs[port_name] = validator(validated_outputs[port_name])
        return validated_outputs


node_registry = NodeRegistry()

