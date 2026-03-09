from __future__ import annotations

from typing import Any

from ParaGraph.server.entities.workflow import WorkflowEdge, WorkflowGraph, WorkflowNode, WorkflowPosition
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.workflow import executor


###############################################################################
class FakeLLMClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    # -------------------------------------------------------------------------
    def check_model_availability(self, name: str, auto_pull: bool = True) -> bool:
        _ = name
        _ = auto_pull
        return True

    # -------------------------------------------------------------------------
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "format": format,
                "options": options,
            }
        )
        return self.response_text


# -----------------------------------------------------------------------------
def build_node(node_id: str, node_type: str, params: dict[str, Any]) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type=node_type,
        position=WorkflowPosition(x=0, y=0),
        params=params,
    )


# -----------------------------------------------------------------------------
def build_edge(edge_id: str, source: str, source_handle: str, target: str, target_handle: str) -> WorkflowEdge:
    return WorkflowEdge(
        id=edge_id,
        source=source,
        sourceHandle=source_handle,
        target=target,
        targetHandle=target_handle,
    )


# -----------------------------------------------------------------------------
def build_supported_graph() -> WorkflowGraph:
    return WorkflowGraph(
        nodes=[
            build_node("prompt_1", "Prompt", {"text": "Summarize this"}),
            build_node("llm_1", "LLM", {"provider": "ollama", "model": "llama3.2", "temperature": 0.1}),
            build_node("output_1", "Output", {}),
        ],
        edges=[
            build_edge("edge_1", "prompt_1", "prompt_out", "llm_1", "prompt_in"),
            build_edge("edge_2", "llm_1", "response_out", "output_1", "text_in"),
        ],
    )


###############################################################################
def test_validate_workflow_graph_accepts_supported_executor_graph() -> None:
    response = executor.validate_workflow_graph(build_supported_graph())

    assert response.valid is True
    assert response.errors == []


# -----------------------------------------------------------------------------
def test_validate_workflow_graph_rejects_cycles() -> None:
    graph = WorkflowGraph(
        nodes=[
            build_node("prompt_1", "Prompt", {"text": "Loop"}),
            build_node("llm_1", "LLM", {}),
        ],
        edges=[
            build_edge("edge_1", "prompt_1", "prompt_out", "llm_1", "prompt_in"),
            build_edge("edge_2", "llm_1", "response_out", "prompt_1", "prompt_out"),
        ],
    )

    response = executor.validate_workflow_graph(graph)

    assert response.valid is False
    assert "Workflow graph contains a cycle" in response.errors


# -----------------------------------------------------------------------------
def test_execute_workflow_graph_runs_llm_and_collects_outputs(
    monkeypatch,
    job_state_factory,
) -> None:
    fake_client = FakeLLMClient("Structured response")
    monkeypatch.setattr(executor, "select_llm_provider", lambda provider: fake_client)
    job_state_factory("job-executor", "workflow")

    result = executor.execute_workflow_graph(build_supported_graph(), job_id="job-executor")
    snapshot = job_manager.get_job_status("job-executor")

    assert result == {"outputs": {"output_1": {"text": "Structured response"}}}
    assert snapshot is not None
    assert snapshot["progress"] == 100.0
    assert snapshot["result"] == {"outputs": {"output_1": {"text": "Structured response"}}}
    assert fake_client.calls == [
        {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Summarize this"}],
            "format": None,
            "options": {"temperature": 0.1},
        }
    ]
