from __future__ import annotations

import time
from threading import Thread

from fastapi.testclient import TestClient

from ParaGraph.server.domain.nodecatalog import ProviderModelDefinition
from ParaGraph.server.services.runtime.events import execution_event_service
from ParaGraph.server.services.workflow import nodes as node_module



def _build_definition() -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "system_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "You are concise."},
            },
            {
                "node_id": "user_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Say hello from e2e"},
            },
            {
                "node_id": "provider_1",
                "node_type": "MODEL_PROVIDER",
                "node_version": 1,
                "parameters": {"provider": "ollama", "model_name": "llama3.2"},
            },
            {
                "node_id": "chat_1",
                "node_type": "LLM_CHAT",
                "node_version": 1,
                "parameters": {"context_window": 0, "max_tokens": 64, "use_reasoning": False},
            },
            {
                "node_id": "output_1",
                "node_type": "TEXT_OUTPUT",
                "node_version": 1,
                "parameters": {},
            },
        ],
        "connections": [
            {
                "from_node": "provider_1",
                "connection_type": "controller",
                "from_controller": "model",
                "to_node": "chat_1",
                "to_controller": "model",
            },
            {
                "from_node": "user_1",
                "from_output": "text",
                "to_node": "chat_1",
                "to_input": "user_prompt",
            },
            {
                "from_node": "system_1",
                "from_output": "text",
                "to_node": "chat_1",
                "to_input": "system_prompt",
            },
            {
                "from_node": "chat_1",
                "from_output": "response",
                "to_node": "output_1",
                "to_input": "text",
            },
        ],
        "metadata": {},
    }



def _poll_run_until_terminal(client: TestClient, run_id: str, timeout_s: float = 3.0) -> list[dict[str, object]]:
    deadline = time.monotonic() + timeout_s
    snapshots: list[dict[str, object]] = []

    while time.monotonic() < deadline:
        response = client.get(f"/executions/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        snapshots.append(payload)
        if payload["status"] not in {"queued", "running"}:
            return snapshots
        time.sleep(0.01)

    raise AssertionError(f"Run {run_id} did not reach terminal state within {timeout_s}s")



def test_execution_lifecycle_end_to_end_with_websocket_replay(client: TestClient, monkeypatch) -> None:
    def _model_definition(provider: str, model: str, session_name: str = "default", timeout_s: float | None = None) -> ProviderModelDefinition:
        _ = session_name
        return ProviderModelDefinition(
            provider=provider,
            model=model,
            label=f"{provider}:{model}",
            supports_image=False,
            supports_reasoning=False,
            supports_structured_output=True,
            timeout_s=timeout_s,
        )

    monkeypatch.setattr(node_module.provider_service, "validate_model_request", lambda **kwargs: None)
    monkeypatch.setattr(node_module.provider_service, "get_model_metadata", _model_definition)
    monkeypatch.setattr(node_module.provider_service, "build_model_definition", _model_definition)
    monkeypatch.setattr(node_module.provider_service, "chat", lambda **kwargs: "Hello from deterministic e2e")

    compile_response = client.post("/executions/compile", json={"definition": _build_definition()})
    assert compile_response.status_code == 200
    compile_payload = compile_response.json()
    assert compile_payload["valid"] is True
    plan = compile_payload["plan"]
    assert isinstance(plan, dict)

    start_response = client.post("/executions", json={"workflow_id": "wf-e2e", "plan": plan})
    assert start_response.status_code == 202
    run_id = start_response.json()["run_id"]

    snapshots = _poll_run_until_terminal(client, run_id)
    statuses = {snapshot["status"] for snapshot in snapshots}
    assert len(snapshots) >= 1
    assert "completed" in statuses
    assert snapshots[-1]["status"] == "completed"
    assert snapshots[-1]["outputs"] == {"output_1": {"text": "Hello from deterministic e2e"}}

    events_response = client.get(f"/executions/{run_id}/events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    event_types = [event["event_type"] for event in events_payload["events"]]
    assert event_types[0] == "execution.queued"
    assert event_types[-1] == "execution.completed"

    sequences = [event["sequence"] for event in events_payload["events"]]
    assert sequences == list(range(1, len(sequences) + 1))

    with client.websocket_connect(f"/executions/ws/runs/{run_id}") as websocket:
        replayed = [websocket.receive_json() for _ in events_payload["events"]]

    assert [event["sequence"] for event in replayed] == sequences

    with client.websocket_connect(f"/executions/ws/runs/{run_id}?replay=false") as websocket:
        synthetic_holder: dict[str, object] = {}

        def _publish_after_subscribe() -> None:
            time.sleep(0.02)
            synthetic_holder["event"] = execution_event_service.publish(
                run_id=run_id,
                event_type="execution.step.progress",
                step_id="chat_1",
                payload={"progress": 50.0},
            )

        publish_thread = Thread(target=_publish_after_subscribe, daemon=True)
        publish_thread.start()
        streamed = websocket.receive_json()
        publish_thread.join(timeout=1.0)

    assert streamed["event_type"] == "execution.step.progress"
    assert streamed["step_id"] == "chat_1"
    synthetic = synthetic_holder.get("event")
    assert synthetic is not None
    assert streamed["sequence"] == synthetic.sequence
    assert streamed["payload"] == {"progress": 50.0}
