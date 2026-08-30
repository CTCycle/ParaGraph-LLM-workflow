from __future__ import annotations

import importlib.util
from functools import partial
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from server.common import path as common_path
from server.contracts.node_catalog import NodeCatalogResponse, NodeManifest
from server.contracts.workflow_payloads import validate_data_type
from server.repositories.workflow.node_manifest import (
    NodeManifestRepository,
    node_manifest_repository,
)
from server.services.workflow.node_handlers import NODE_HANDLERS
from server.services.workflow.nodes.handler import NodeHandler
from server.services.workflow.nodes.execution_context import (
    reset_execution_context,
    set_execution_context,
)
from server.services.workflow.vector_stores import get_vector_store_capabilities


MODEL_NODE_IDS = {"LLM_CHAT", "LLM_STRUCTURED"}
STRUCTURED_NODE_IDS = {"LLM_STRUCTURED"}


###############################################################################
def _format_parameter_validation_error(error: ValidationError) -> str:
    issues = error.errors()
    if not issues:
        return str(error)

    messages: list[str] = []
    for issue in issues[:3]:
        location = ".".join(
            str(part) for part in issue.get("loc", ()) if part != "__root__"
        )
        message = str(issue.get("msg") or "Invalid parameter")
        messages.append(f"{location}: {message}" if location else message)

    if len(issues) > 3:
        messages.append(f"(+{len(issues) - 3} more)")
    return "; ".join(messages)


###############################################################################
def _execute_plugin_manifest(
    registry: NodeRegistry,
    manifest: NodeManifest,
    parameters: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    callable_executor = registry._load_plugin_callable(manifest)
    result = callable_executor(dict(parameters), dict(inputs))
    if not isinstance(result, dict):
        raise ValueError(
            f"Node '{manifest.id}' plugin entrypoint must return an object"
        )
    return result


###############################################################################
class NodeRegistry:
    # -------------------------------------------------------------------------
    def __init__(
        self, manifest_repository: NodeManifestRepository | None = None
    ) -> None:
        self._manifest_repository = manifest_repository or node_manifest_repository
        self._definitions: dict[tuple[str, int], NodeManifest] = {}
        self._manifest_paths: dict[tuple[str, int], Path] = {}
        self._plugin_handlers: dict[tuple[str, int], NodeHandler] = {}
        self._plugin_cache: dict[Path, tuple[int, Any]] = {}
        common_path.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        self.reload()

    # -------------------------------------------------------------------------
    def reload(self) -> None:
        definitions: dict[tuple[str, int], NodeManifest] = {}
        manifest_paths: dict[tuple[str, int], Path] = {}
        for path in self._manifest_repository.list_manifest_files():
            manifest = self._manifest_repository.load_manifest(path)
            key = (manifest.id, manifest.version)
            if key in definitions:
                raise ValueError(
                    f"Duplicate node manifest detected for {manifest.id} v{manifest.version}"
                )
            self._assert_executor_known(manifest, source_path=path)
            definitions[key] = manifest
            manifest_paths[key] = path
        self._definitions = definitions
        self._manifest_paths = manifest_paths
        self._plugin_handlers = {}

    # -------------------------------------------------------------------------
    def _assert_executor_known(
        self, manifest: NodeManifest, *, source_path: Path | None = None
    ) -> None:
        plugin = manifest.runtime.plugin
        if plugin is not None:
            self._resolve_plugin_script_path(
                manifest, source_path=source_path, validate_exists=True
            )
            return
        if manifest.runtime.executor_key not in NODE_HANDLERS:
            raise ValueError(
                f"Unknown executor_key '{manifest.runtime.executor_key}' for node '{manifest.id}'"
            )

    # -------------------------------------------------------------------------
    def _manifest_source_path(self, manifest: NodeManifest) -> Path:
        key = (manifest.id, manifest.version)
        path = self._manifest_paths.get(key)
        if path is None:
            raise ValueError(
                f"Missing manifest source path for node '{manifest.id}' v{manifest.version}"
            )
        return path

    # -------------------------------------------------------------------------
    def _resolve_plugin_script_path(
        self,
        manifest: NodeManifest,
        *,
        source_path: Path | None = None,
        validate_exists: bool,
    ) -> Path:
        plugin = manifest.runtime.plugin
        if plugin is None:
            raise ValueError(f"Node '{manifest.id}' does not define a runtime plugin")

        raw_script_path = plugin.script_path.strip()
        if not raw_script_path:
            raise ValueError(
                f"Node '{manifest.id}' plugin script_path must not be empty"
            )

        script_path = Path(raw_script_path).expanduser()
        if script_path.is_absolute():
            raise ValueError(
                f"Node '{manifest.id}' plugin script_path must be relative to the manifest file for portability"
            )

        manifest_path = source_path or self._manifest_source_path(manifest)
        resolved = (manifest_path.parent / script_path).resolve()
        if validate_exists and (not resolved.exists() or not resolved.is_file()):
            raise ValueError(
                f"Node '{manifest.id}' plugin script not found: {resolved}"
            )
        return resolved

    # -------------------------------------------------------------------------
    def _load_plugin_callable(self, manifest: NodeManifest):
        plugin = manifest.runtime.plugin
        if plugin is None:
            raise ValueError(f"Node '{manifest.id}' does not define a runtime plugin")

        script_path = self._resolve_plugin_script_path(manifest, validate_exists=True)
        modified_at = script_path.stat().st_mtime_ns
        cached = self._plugin_cache.get(script_path)
        if cached is not None and cached[0] == modified_at:
            return cached[1]

        module_name = f"paragraph_node_plugin_{manifest.id.lower()}_{manifest.version}_{abs(hash(str(script_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ValueError(
                f"Unable to load plugin module for node '{manifest.id}' from {script_path}"
            )

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        entrypoint = plugin.entrypoint.strip() or "execute"
        candidate = getattr(module, entrypoint, None)
        if not callable(candidate):
            raise ValueError(
                f"Node '{manifest.id}' plugin entrypoint '{entrypoint}' is missing or not callable in {script_path}"
            )

        self._plugin_cache[script_path] = (modified_at, candidate)
        return candidate

    # -------------------------------------------------------------------------
    def _build_plugin_handler(self, manifest: NodeManifest) -> NodeHandler:
        key = (manifest.id, manifest.version)
        cached = self._plugin_handlers.get(key)
        if cached is not None:
            return cached

        handler = NodeHandler(
            executor=partial(_execute_plugin_manifest, self, manifest)
        )
        self._plugin_handlers[key] = handler
        return handler

    # -------------------------------------------------------------------------
    def _handler_for_manifest(self, manifest: NodeManifest) -> NodeHandler:
        if manifest.runtime.plugin is not None:
            return self._build_plugin_handler(manifest)
        return NODE_HANDLERS[manifest.runtime.executor_key]

    # -------------------------------------------------------------------------
    def get(self, node_type: str, version: int | None = None) -> NodeManifest | None:
        if version is not None:
            return self._definitions.get((node_type, version))
        matching = [
            manifest
            for (manifest_id, _), manifest in self._definitions.items()
            if manifest_id == node_type
        ]
        if not matching:
            return None
        return sorted(matching, key=lambda item: item.version)[-1]

    # -------------------------------------------------------------------------
    def list(self) -> list[NodeManifest]:
        return sorted(
            self._definitions.values(),
            key=lambda item: (item.category, item.name, item.version),
        )

    # -------------------------------------------------------------------------
    def catalog_response(self) -> NodeCatalogResponse:
        return NodeCatalogResponse(
            nodes=self.list(),
            vector_store_capabilities=get_vector_store_capabilities(),
        )

    # -------------------------------------------------------------------------
    def import_manifest(self, manifest: NodeManifest) -> NodeManifest:
        if self.get(manifest.id, manifest.version) is not None:
            raise ValueError(
                f"Node manifest already exists for {manifest.id} v{manifest.version}"
            )

        path = self._manifest_repository.path_for_manifest(manifest)
        self._assert_executor_known(manifest, source_path=path)
        self._manifest_repository.save_manifest(manifest)

        try:
            self.reload()
            created = self.get(manifest.id, manifest.version)
            if created is None:
                raise ValueError(
                    f"Imported node manifest could not be reloaded: {manifest.id} v{manifest.version}"
                )
        except Exception as exc:
            self._manifest_repository.delete_manifest(path)
            self.reload()
            raise ValueError(
                f"Failed to persist imported node manifest: {exc}"
            ) from exc

        return created

    # -------------------------------------------------------------------------
    def validate_parameters(
        self, node_type: str, node_version: int, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        manifest = self.get(node_type, node_version)
        if manifest is None:
            raise ValueError(f"Unknown node type/version '{node_type}' v{node_version}")
        handler = self._handler_for_manifest(manifest)
        payload = dict(parameters)
        if handler.parameter_model is not None:
            try:
                payload = handler.parameter_model.model_validate(payload).model_dump(
                    mode="json"
                )
            except ValidationError as exc:
                raise ValueError(_format_parameter_validation_error(exc)) from exc
        self._validate_parameter_constraints(manifest, payload)
        return payload

    # -------------------------------------------------------------------------
    def _validate_parameter_constraints(
        self, manifest: NodeManifest, parameters: dict[str, Any]
    ) -> None:
        for parameter in manifest.parameters:
            if parameter.name not in parameters:
                continue
            value = parameters[parameter.name]
            constraints = parameter.constraints or {}
            if (
                parameter.ui_control == "number"
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                minimum = constraints.get("min")
                maximum = constraints.get("max")
                if minimum is not None and value < minimum:
                    raise ValueError(
                        f"Parameter '{parameter.name}' must be greater than or equal to {minimum}"
                    )
                if maximum is not None and value > maximum:
                    raise ValueError(
                        f"Parameter '{parameter.name}' must be less than or equal to {maximum}"
                    )
            options = constraints.get("options")
            if isinstance(options, list) and options and value not in options:
                raise ValueError(
                    f"Parameter '{parameter.name}' must be one of: {', '.join(str(item) for item in options)}"
                )

    # -------------------------------------------------------------------------
    def _validate_ports(
        self, manifest: NodeManifest, values: dict[str, Any], *, label: str
    ) -> dict[str, Any]:
        if label == "input":
            ports = manifest.inputs
        elif label == "output":
            ports = manifest.outputs
        elif label == "controller":
            ports = manifest.controllers
        else:
            raise ValueError(f"Unsupported port label '{label}'")
        validated: dict[str, Any] = {}
        for port in ports:
            if port.name not in values:
                if port.required and label == "output":
                    raise ValueError(
                        f"Node '{manifest.id}' did not produce required output '{port.name}'"
                    )
                continue
            value = values[port.name]
            if value is None and not port.required:
                continue
            if port.accepts_multiple and isinstance(value, list):
                validated[port.name] = [
                    validate_data_type(port.data_type, item) for item in value
                ]
            else:
                validated[port.name] = validate_data_type(port.data_type, value)
        return validated

    # -------------------------------------------------------------------------
    def execute(
        self,
        node_type: str,
        node_version: int,
        parameters: dict[str, Any],
        inputs: dict[str, Any],
        controllers: dict[str, Any] | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        manifest = self.get(node_type, node_version)
        if manifest is None:
            raise ValueError(f"Unknown node type/version '{node_type}' v{node_version}")
        handler = self._handler_for_manifest(manifest)
        validated_parameters = self.validate_parameters(
            node_type, node_version, parameters
        )
        validated_inputs = self._validate_ports(manifest, inputs, label="input")
        validated_controllers = self._validate_ports(
            manifest, controllers or {}, label="controller"
        )

        overlapping_keys = set(validated_inputs).intersection(validated_controllers)
        if overlapping_keys:
            merged = ", ".join(sorted(overlapping_keys))
            raise ValueError(
                f"Node '{manifest.id}' has overlapping input/controller names: {merged}"
            )

        execution_inputs = {**validated_inputs, **validated_controllers}
        for port_name, validator in handler.input_validators.items():
            if port_name in execution_inputs:
                execution_inputs[port_name] = validator(execution_inputs[port_name])

        token = set_execution_context(context or {})
        try:
            outputs = handler.executor(validated_parameters, execution_inputs)
            if not isinstance(outputs, dict):
                raise ValueError(f"Node '{manifest.id}' executor must return an object")
            declared_output_names = {
                port.name for port in [*manifest.outputs, *manifest.controllers]
            }
            undeclared_output_names = sorted(
                set(outputs).difference(declared_output_names)
            )
            if undeclared_output_names:
                joined = ", ".join(undeclared_output_names)
                raise ValueError(
                    f"Node '{manifest.id}' produced undeclared outputs: {joined}"
                )
            validated_outputs = self._validate_ports(manifest, outputs, label="output")
            validated_controller_outputs = self._validate_ports(
                manifest, outputs, label="controller"
            )
            for port_name, validator in handler.output_validators.items():
                if port_name in validated_outputs:
                    validated_outputs[port_name] = validator(
                        validated_outputs[port_name]
                    )
            return {**validated_outputs, **validated_controller_outputs}
        finally:
            reset_execution_context(token)


node_registry = NodeRegistry()
