from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from ParaGraph.server.domain.workflow import (
    CatalogResponse,
    NodeParameterSchema,
    NodePort,
    ValidateWorkflowResponse,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeDefinition,
)
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.llm.providers import LLMError, OllamaError, select_llm_provider


SUPPORTED_EXECUTOR_NODE_TYPES = {"Prompt", "LLM", "Output"}
ALLOWED_CATEGORY_EDGES = {
    ("input", "process"),
    ("process", "process"),
    ("process", "output"),
}


###############################################################################
CATALOG_DEFINITIONS = [
    WorkflowNodeDefinition(
        type="Prompt",
        label="Prompt",
        description="Input prompt text",
        category="input",
        ports=[
            NodePort(handle="prompt_out", label="Prompt", direction="output", data_type="text"),
        ],
        parameters=[
            NodeParameterSchema(
                key="text",
                label="Prompt",
                field_type="textarea",
                required=True,
                default="",
                description="Text sent to the LLM node",
            ),
        ],
    ),
    WorkflowNodeDefinition(
        type="LLM",
        label="LLM",
        description="Large language model call",
        category="process",
        ports=[
            NodePort(handle="prompt_in", label="Prompt", direction="input", data_type="text"),
            NodePort(handle="response_out", label="Response", direction="output", data_type="text"),
        ],
        parameters=[
            NodeParameterSchema(
                key="provider",
                label="Provider",
                field_type="select",
                default="ollama",
                options=["ollama", "openai", "gemini", "anthropic"],
            ),
            NodeParameterSchema(
                key="model",
                label="Model",
                field_type="text",
                default="llama3.2",
            ),
            NodeParameterSchema(
                key="system_prompt",
                label="System Prompt",
                field_type="textarea",
                default="",
            ),
            NodeParameterSchema(
                key="format",
                label="Output Format",
                field_type="select",
                default="text",
                options=["text", "json"],
            ),
            NodeParameterSchema(
                key="temperature",
                label="Temperature",
                field_type="number",
                default=0.2,
            ),
        ],
    ),
    WorkflowNodeDefinition(
        type="Retrieval",
        label="Retrieval",
        description="Retriever placeholder (catalog-visible only for MVP)",
        category="process",
        ports=[
            NodePort(handle="query_in", label="Query", direction="input", data_type="text"),
            NodePort(handle="context_out", label="Context", direction="output", data_type="text"),
        ],
        parameters=[
            NodeParameterSchema(key="index_name", label="Index", field_type="text", default=""),
        ],
    ),
    WorkflowNodeDefinition(
        type="VectorDB",
        label="VectorDB",
        description="Vector database placeholder (catalog-visible only for MVP)",
        category="process",
        ports=[
            NodePort(handle="query_in", label="Query", direction="input", data_type="text"),
            NodePort(handle="context_out", label="Context", direction="output", data_type="text"),
        ],
        parameters=[
            NodeParameterSchema(key="collection", label="Collection", field_type="text", default=""),
        ],
    ),
    WorkflowNodeDefinition(
        type="Output",
        label="Output",
        description="Final output node",
        category="output",
        ports=[
            NodePort(handle="text_in", label="Text", direction="input", data_type="text"),
        ],
        parameters=[
            NodeParameterSchema(
                key="outputText",
                label="Output",
                field_type="textarea",
                default="",
                description="Execution result is written here",
            ),
        ],
    ),
]
CATALOG_BY_TYPE = {definition.type: definition for definition in CATALOG_DEFINITIONS}


# -----------------------------------------------------------------------------
def get_catalog_response() -> CatalogResponse:
    return CatalogResponse(nodes=CATALOG_DEFINITIONS)


# -----------------------------------------------------------------------------
def _ports_map(definition: WorkflowNodeDefinition, direction: str) -> dict[str, NodePort]:
    return {port.handle: port for port in definition.ports if port.direction == direction}


# -----------------------------------------------------------------------------
def _topological_sort(node_ids: list[str], edges: list[WorkflowEdge]) -> list[str]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}

    for edge in edges:
        if edge.source not in indegree or edge.target not in indegree:
            continue
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    queue = deque(sorted([node_id for node_id, degree in indegree.items() if degree == 0]))
    ordered: list[str] = []

    while queue:
        current = queue.popleft()
        ordered.append(current)
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(ordered) != len(node_ids):
        raise ValueError("Workflow graph contains a cycle")
    return ordered


# -----------------------------------------------------------------------------
def validate_workflow_graph(graph: WorkflowGraph) -> ValidateWorkflowResponse:
    errors: list[str] = []

    node_ids_seen: set[str] = set()
    edge_ids_seen: set[str] = set()

    for node in graph.nodes:
        if node.id in node_ids_seen:
            errors.append(f"Duplicate node id: {node.id}")
        node_ids_seen.add(node.id)
        if node.type not in CATALOG_BY_TYPE:
            errors.append(f"Unknown node type '{node.type}' for node '{node.id}'")

    for edge in graph.edges:
        if edge.id in edge_ids_seen:
            errors.append(f"Duplicate edge id: {edge.id}")
        edge_ids_seen.add(edge.id)

    node_by_id = {node.id: node for node in graph.nodes}

    for edge in graph.edges:
        source_node = node_by_id.get(edge.source)
        target_node = node_by_id.get(edge.target)

        if source_node is None:
            errors.append(f"Edge '{edge.id}' references missing source node '{edge.source}'")
            continue
        if target_node is None:
            errors.append(f"Edge '{edge.id}' references missing target node '{edge.target}'")
            continue

        source_definition = CATALOG_BY_TYPE.get(source_node.type)
        target_definition = CATALOG_BY_TYPE.get(target_node.type)
        if source_definition is None or target_definition is None:
            continue

        if source_definition.category == "output":
            errors.append(f"Node '{source_node.id}' is output and cannot have outgoing edges")

        category_pair = (source_definition.category, target_definition.category)
        if category_pair not in ALLOWED_CATEGORY_EDGES:
            errors.append(
                f"Invalid category flow '{source_definition.category}->{target_definition.category}' on edge '{edge.id}'"
            )

        source_outputs = _ports_map(source_definition, "output")
        target_inputs = _ports_map(target_definition, "input")

        source_port = source_outputs.get(edge.sourceHandle)
        if source_port is None:
            errors.append(
                f"Edge '{edge.id}' references unknown source handle '{edge.sourceHandle}' on node '{source_node.id}'"
            )
            continue

        target_port = target_inputs.get(edge.targetHandle)
        if target_port is None:
            errors.append(
                f"Edge '{edge.id}' references unknown target handle '{edge.targetHandle}' on node '{target_node.id}'"
            )
            continue

        compatible = (
            source_port.data_type == target_port.data_type
            or source_port.data_type == "any"
            or target_port.data_type == "any"
        )
        if not compatible:
            errors.append(
                f"Type mismatch on edge '{edge.id}': {source_port.data_type} -> {target_port.data_type}"
            )

    try:
        _topological_sort([node.id for node in graph.nodes], graph.edges)
    except ValueError as exc:
        errors.append(str(exc))

    connected_ids: set[str] = set()
    for edge in graph.edges:
        connected_ids.add(edge.source)
        connected_ids.add(edge.target)

    for node_id in sorted(connected_ids):
        node = node_by_id.get(node_id)
        if node is None:
            continue
        if node.type not in SUPPORTED_EXECUTOR_NODE_TYPES:
            errors.append(
                f"Node '{node.id}' type '{node.type}' is connected but not supported by the MVP executor"
            )

    return ValidateWorkflowResponse(valid=not errors, errors=errors)


# -----------------------------------------------------------------------------
def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# -----------------------------------------------------------------------------
def _collect_input_text(
    node_id: str,
    incoming_by_target: dict[str, list[WorkflowEdge]],
    outputs_by_node: dict[str, dict[str, Any]],
    expected_handle: str | None = None,
) -> str:
    collected: list[str] = []
    for edge in sorted(incoming_by_target.get(node_id, []), key=lambda item: item.id):
        if expected_handle and edge.targetHandle != expected_handle:
            continue
        source_output = outputs_by_node.get(edge.source, {})
        text = source_output.get("text")
        if text:
            collected.append(str(text))
    return "\n".join(collected).strip()


# -----------------------------------------------------------------------------
def _default_model(provider: str) -> str:
    normalized = provider.lower()
    if normalized == "openai":
        return "gpt-4o-mini"
    if normalized == "gemini":
        return "gemini-1.5-flash"
    if normalized == "anthropic":
        return "claude-3-5-sonnet-latest"
    return "llama3.2"


# -----------------------------------------------------------------------------
def _run_llm_node(node: WorkflowNode, prompt_text: str) -> str:
    params = node.params
    provider = str(params.get("provider", "ollama")).lower()
    model = str(params.get("model") or _default_model(provider))

    system_prompt = str(params.get("system_prompt", "")).strip()
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt_text})

    options: dict[str, Any] = {"temperature": _coerce_float(params.get("temperature"), 0.2)}
    result_format = str(params.get("format", "text")).lower()
    request_format = "json" if result_format == "json" else None

    client = select_llm_provider(provider)
    if provider == "ollama":
        auto_pull = bool(params.get("auto_pull", True))
        if hasattr(client, "check_model_availability"):
            client.check_model_availability(model, auto_pull=auto_pull)

    return client.chat(model=model, messages=messages, format=request_format, options=options)


# -----------------------------------------------------------------------------
def execute_workflow_graph(graph: WorkflowGraph, job_id: str) -> dict[str, Any]:
    validation = validate_workflow_graph(graph)
    if not validation.valid:
        joined = "; ".join(validation.errors)
        raise ValueError(f"Workflow validation failed: {joined}")

    node_by_id = {node.id: node for node in graph.nodes}
    ordered_node_ids = _topological_sort([node.id for node in graph.nodes], graph.edges)

    incoming_by_target: dict[str, list[WorkflowEdge]] = defaultdict(list)
    for edge in graph.edges:
        incoming_by_target[edge.target].append(edge)

    outputs_by_node: dict[str, dict[str, Any]] = {}
    output_payload: dict[str, dict[str, str]] = {}

    total_nodes = len(ordered_node_ids) or 1
    for index, node_id in enumerate(ordered_node_ids, start=1):
        if job_manager.should_stop(job_id):
            return {}

        node = node_by_id[node_id]
        node_type = node.type

        if node_type == "Prompt":
            prompt_text = str(node.params.get("text") or node.params.get("prompt") or "").strip()
            outputs_by_node[node.id] = {"text": prompt_text}

        elif node_type == "LLM":
            input_text = _collect_input_text(node.id, incoming_by_target, outputs_by_node, expected_handle="prompt_in")
            if not input_text:
                input_text = str(node.params.get("text") or node.params.get("prompt") or "").strip()
            if not input_text:
                raise ValueError(f"LLM node '{node.id}' does not have input text")
            try:
                llm_text = _run_llm_node(node, input_text)
            except (LLMError, OllamaError) as exc:
                raise ValueError(str(exc)) from exc
            outputs_by_node[node.id] = {"text": llm_text}

        elif node_type == "Output":
            output_text = _collect_input_text(node.id, incoming_by_target, outputs_by_node, expected_handle="text_in")
            outputs_by_node[node.id] = {"text": output_text}
            output_payload[node.id] = {"text": output_text}
            job_manager.update_result(job_id, {"outputs": dict(output_payload)})

        else:
            outputs_by_node[node.id] = {"text": str(node.params.get("text", "")).strip()}

        progress = (index / total_nodes) * 100.0
        job_manager.update_progress(job_id, progress)

    return {"outputs": output_payload}
