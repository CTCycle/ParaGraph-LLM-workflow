from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.services.workflow.provider import provider_service


Executor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

NODE_ROOT = Path(RESOURCES_PATH) / "nodes"
ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value)


def _prompt_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    return {"text": _coerce_text(parameters.get("prompt_text", "")).strip()}


def _image_input_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    path = _coerce_text(parameters.get("file_path", "")).strip()
    return {"image": {"path": path}}


def _llm_generate_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = _coerce_text(inputs.get("prompt") or parameters.get("prompt_fallback", "")).strip()
    if not prompt:
        raise ValueError("LLM_GENERATE requires a prompt input")

    provider = _coerce_text(parameters.get("provider", "ollama")).lower()
    model_name = _coerce_text(parameters.get("model_name", "llama3.2"))
    system_prompt = _coerce_text(parameters.get("system_prompt", "")).strip()
    temperature = float(parameters.get("temperature", 0.2) or 0.2)
    max_tokens = int(float(parameters.get("max_tokens", 512) or 512))
    top_p = float(parameters.get("top_p", 1.0) or 1.0)

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    text = provider_service.chat(
        provider=provider,
        model=model_name,
        messages=messages,
        response_format=None,
        options={"temperature": temperature, "max_output_tokens": max_tokens, "top_p": top_p},
    )
    return {"response": text}


def _embedding_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = _coerce_text(inputs.get("text") or "").strip()
    if not text:
        raise ValueError("EMBEDDING_MODEL requires text input")
    provider = _coerce_text(parameters.get("provider", "ollama")).lower()
    model_name = _coerce_text(parameters.get("model_name", "nomic-embed-text"))
    return {"embedding": provider_service.embed_text(provider=provider, model=model_name, text=text)}


def _tokenize_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = _coerce_text(inputs.get("text") or "")
    tokens = [index for index, part in enumerate(text.split(), start=1) if part]
    return {"tokens": tokens}


def _text_split_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = _coerce_text(inputs.get("text") or "")
    delimiter = _coerce_text(parameters.get("delimiter", "\n"))
    segments = [segment.strip() for segment in text.split(delimiter) if segment.strip()]
    return {"segments": segments}


def _template_format_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    template = _coerce_text(parameters.get("template", "{input}"))
    value = _coerce_text(inputs.get("input") or "")
    return {"text": template.replace("{input}", value)}


def _save_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = _coerce_text(inputs.get("text") or "")
    storage_path = _coerce_text(parameters.get("storage_path", "saved_text.txt")).strip() or "saved_text.txt"
    destination = (ARTIFACT_ROOT / storage_path).resolve()
    if ARTIFACT_ROOT.resolve() not in destination.parents and destination != ARTIFACT_ROOT.resolve():
        raise ValueError("storage_path must stay inside ParaGraph/resources/artifacts")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return {"artifact": {"path": str(destination.relative_to(ARTIFACT_ROOT.resolve()))}}


def _load_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    storage_path = _coerce_text(parameters.get("storage_path", "saved_text.txt")).strip() or "saved_text.txt"
    source = (ARTIFACT_ROOT / storage_path).resolve()
    if ARTIFACT_ROOT.resolve() not in source.parents and source != ARTIFACT_ROOT.resolve():
        raise ValueError("storage_path must stay inside ParaGraph/resources/artifacts")
    if not source.exists():
        raise ValueError(f"Text artifact not found: {storage_path}")
    return {"text": source.read_text(encoding="utf-8")}


def _text_output_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    return {"result": _coerce_text(inputs.get("text") or "")}


def _image_output_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    image = inputs.get("image") or {}
    return {"result": image}


def _if_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    condition = bool(inputs.get("condition"))
    return {"result": inputs.get("true_value") if condition else inputs.get("false_value")}


def _router_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    value = inputs.get("value")
    expected = _coerce_text(parameters.get("expected_value", ""))
    if _coerce_text(value) == expected:
        return {"matched": value, "unmatched": None}
    return {"matched": None, "unmatched": value}


EXECUTORS: dict[str, Executor] = {
    "prompt": _prompt_executor,
    "image_input": _image_input_executor,
    "llm_generate": _llm_generate_executor,
    "embedding_model": _embedding_executor,
    "tokenize": _tokenize_executor,
    "text_split": _text_split_executor,
    "template_format": _template_format_executor,
    "save_text": _save_text_executor,
    "load_text": _load_text_executor,
    "text_output": _text_output_executor,
    "image_output": _image_output_executor,
    "if": _if_executor,
    "router": _router_executor,
}


class NodeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], NodeManifest] = {}
        NODE_ROOT.mkdir(parents=True, exist_ok=True)
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        self.reload()

    def reload(self) -> None:
        definitions: dict[tuple[str, int], NodeManifest] = {}
        for path in sorted(NODE_ROOT.glob('*.json')):
            manifest = NodeManifest.model_validate_json(path.read_text(encoding='utf-8'))
            key = (manifest.id, manifest.version)
            if key in definitions:
                raise ValueError(f"Duplicate node manifest detected for {manifest.id} v{manifest.version}")
            self._assert_executor_known(manifest)
            definitions[key] = manifest
        self._definitions = definitions

    def _assert_executor_known(self, manifest: NodeManifest) -> None:
        if manifest.runtime.executor_key not in EXECUTORS:
            raise ValueError(f"Unknown executor_key '{manifest.runtime.executor_key}' for node '{manifest.id}'")

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
        path.write_text(json.dumps(manifest.model_dump(mode='json'), indent=2), encoding='utf-8')
        self.reload()
        created = self.get(manifest.id, manifest.version)
        if created is None:
            raise ValueError(f"Imported node manifest could not be reloaded: {manifest.id} v{manifest.version}")
        return created

    def execute(self, executor_key: str, parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        executor = EXECUTORS[executor_key]
        return executor(parameters, inputs)


node_registry = NodeRegistry()
