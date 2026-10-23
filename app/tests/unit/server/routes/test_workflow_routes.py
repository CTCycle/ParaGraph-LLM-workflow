from __future__ import annotations

import time
from fastapi.testclient import TestClient
from server.repositories.workflow.execution_run import ExecutionRunRepository
from pathlib import Path
from collections.abc import Callable
import pytest
from server.contracts.configuration import ProviderConfiguration
from server.contracts.node_catalog import ProviderModelDefinition
from server.services.workflow import provider_service
from server.services.workflow.provider.models import ModelMetadata

# Execution routes

###############################################################################
def test_cancel_paused_run_clears_durable_checkpoint(client: TestClient) -> None:
    compiled = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "gate",
                        "node_type": "HUMAN_REVIEW_GATE",
                        "node_version": 1,
                        "parameters": {},
                    }
                ],
                "connections": [],
                "metadata": {},
            }
        },
    )
    assert compiled.status_code == 200
    started = client.post("/executions", json={"plan": compiled.json()["plan"]})
    assert started.status_code == 202
    run_id = started.json()["run_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        paused = client.get(f"/executions/{run_id}").json()
        if paused["status"] == "paused":
            break
        time.sleep(0.01)
    assert paused["status"] == "paused"
    token = paused["resume_token"]
    cancelled = client.post(f"/executions/{run_id}/cancel")
    assert cancelled.status_code == 200
    restored = ExecutionRunRepository().get_run(run_id)
    assert restored is not None and restored.status == "cancelled"
    assert restored.pause_checkpoint is None and restored.resume_token is None
    assert restored.steps[0].status == "skipped"
    assert restored.steps[0].blocked_reason == "execution_cancelled"
    assert restored.steps[0].resume_token is None
    assert client.get(f"/executions/{run_id}").status_code == 200
    assert (
        client.post(
            f"/executions/{run_id}/resume", json={"resume_token": token}
        ).status_code
        == 409
    )
    assert client.post(f"/executions/{run_id}/cancel").status_code == 409
    events = client.get(f"/executions/{run_id}/events").json()["events"]
    assert [event["event_type"] for event in events][-2:] == [
        "execution.cancellation.requested",
        "execution.cancelled",
    ]

###############################################################################
def _basic_prompt_output_definition() -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "hello"},
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
                "from_node": "prompt_1",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "text",
            }
        ],
        "metadata": {},
    }

###############################################################################
def test_compile_flags_duplicate_connections(client: TestClient) -> None:
    definition = _basic_prompt_output_definition()
    definition["connections"] = [
        {
            "from_node": "prompt_1",
            "from_output": "text",
            "to_node": "output_1",
            "to_input": "text",
        },
        {
            "from_node": "prompt_1",
            "from_output": "text",
            "to_node": "output_1",
            "to_input": "text",
        },
    ]

    response = client.post("/executions/compile", json={"definition": definition})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    codes = {item["code"] for item in payload["diagnostics"]}
    assert "duplicate_connection" in codes

###############################################################################
def test_compile_flags_input_multiplicity_violation(client: TestClient) -> None:
    definition = {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "hello"},
            },
            {
                "node_id": "prompt_2",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "world"},
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
                "from_node": "prompt_1",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "text",
            },
            {
                "from_node": "prompt_2",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "text",
            },
        ],
        "metadata": {},
    }

    response = client.post("/executions/compile", json={"definition": definition})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    codes = {item["code"] for item in payload["diagnostics"]}
    assert "input_multiplicity" in codes

###############################################################################
def test_compile_flags_missing_ports_and_controllers(client: TestClient) -> None:
    missing_source_port = {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "hello"},
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
                "from_node": "prompt_1",
                "from_output": "missing",
                "to_node": "output_1",
                "to_input": "text",
            }
        ],
        "metadata": {},
    }
    response_source = client.post(
        "/executions/compile", json={"definition": missing_source_port}
    )
    source_codes = {item["code"] for item in response_source.json()["diagnostics"]}
    assert "missing_source_port" in source_codes

    missing_target_port = {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "hello"},
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
                "from_node": "prompt_1",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "missing",
            }
        ],
        "metadata": {},
    }
    response_target = client.post(
        "/executions/compile", json={"definition": missing_target_port}
    )
    target_codes = {item["code"] for item in response_target.json()["diagnostics"]}
    assert "missing_target_port" in target_codes

    missing_controller = {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "user_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "say hello"},
            },
            {
                "node_id": "chat_1",
                "node_type": "LLM_CHAT",
                "node_version": 1,
                "parameters": {
                    "context_window": 0,
                    "max_tokens": 16,
                    "use_reasoning": False,
                },
            },
        ],
        "connections": [
            {
                "from_node": "user_1",
                "from_output": "text",
                "to_node": "chat_1",
                "to_input": "user_prompt",
            }
        ],
        "metadata": {},
    }
    response_controller = client.post(
        "/executions/compile", json={"definition": missing_controller}
    )
    controller_codes = {
        item["code"] for item in response_controller.json()["diagnostics"]
    }
    assert (
        "missing_required_controller" in controller_codes
        or "missing_model_selection" in controller_codes
    )

###############################################################################
def test_get_execution_returns_404_for_unknown_run(client: TestClient) -> None:
    response = client.get("/executions/run-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found: run-missing"

###############################################################################
def test_execution_session_id_round_trips_through_execution_endpoints(
    client: TestClient,
) -> None:
    compile_response = client.post(
        "/executions/compile", json={"definition": _basic_prompt_output_definition()}
    )
    assert compile_response.status_code == 200
    payload = compile_response.json()
    assert payload["valid"] is True
    plan = payload["plan"]
    assert isinstance(plan, dict)

    session_id = "session-route-test"
    start_response = client.post(
        "/executions",
        json={
            "workflow_id": "wf-route-test",
            "execution_session_id": session_id,
            "plan": plan,
        },
    )
    assert start_response.status_code == 202
    started = start_response.json()
    assert started["execution_session_id"] == session_id

    run_id = started["run_id"]
    deadline = time.monotonic() + 2.0
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        run_response = client.get(f"/executions/{run_id}")
        if run_response.status_code == 200:
            last_payload = run_response.json()
            if last_payload.get("execution_session_id") == session_id:
                break
        time.sleep(0.01)

    assert last_payload is not None
    assert last_payload["execution_session_id"] == session_id

###############################################################################
def test_execution_request_id_correlates_response_run_and_events(
    client: TestClient,
) -> None:
    compile_response = client.post(
        "/executions/compile", json={"definition": _basic_prompt_output_definition()}
    )
    assert compile_response.status_code == 200
    plan = compile_response.json()["plan"]

    request_id = "qa-request-123"
    start_response = client.post(
        "/executions",
        headers={"X-Request-ID": request_id},
        json={
            "workflow_id": "wf-request-id-test",
            "execution_session_id": "session-request-id-test",
            "plan": plan,
        },
    )

    assert start_response.status_code == 202
    assert start_response.headers["X-Request-ID"] == request_id
    started = start_response.json()
    assert started["request_id"] == request_id

    run_id = started["run_id"]
    deadline = time.monotonic() + 2.0
    run_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        run_response = client.get(f"/executions/{run_id}")
        assert run_response.status_code == 200
        run_payload = run_response.json()
        if run_payload["status"] == "completed":
            break
        time.sleep(0.01)

    assert run_payload is not None
    assert run_payload["request_id"] == request_id

    events_response = client.get(f"/executions/{run_id}/events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload["request_id"] == request_id
    assert {event["request_id"] for event in events_payload["events"]} == {request_id}

# Fragmentation workflow routes

###############################################################################
def build_fragmentation_definition(
    source_path: str, output_path: str
) -> dict[str, object]:
    source_folder = str(Path(source_path).resolve().parent)
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "doc_1",
                "node_type": "LOAD_DOCUMENTS",
                "node_version": 1,
                "parameters": {"folder_path": source_folder, "recursive": False},
            },
            {
                "node_id": "split_1",
                "node_type": "BY_DELIMITER_CHUNKS",
                "node_version": 1,
                "parameters": {
                    "delimiter": "period",
                    "keep_delimiter": False,
                    "drop_empty": True,
                    "max_chunk_size": 0,
                    "overflow_strategy": "split_further",
                },
            },
            {
                "node_id": "merge_1",
                "node_type": "MERGE_SMALL_CHUNKS",
                "node_version": 1,
                "parameters": {
                    "target_chunk_size": 8,
                    "unit": "words",
                    "max_chunk_size": 0,
                    "merge_strategy": "sequential",
                    "preserve_boundaries": True,
                },
            },
            {
                "node_id": "save_1",
                "node_type": "SAVE_AS_FOLDER",
                "node_version": 1,
                "parameters": {
                    "output_path": output_path,
                    "extension": ".md",
                },
            },
            {
                "node_id": "output_1",
                "node_type": "JSON_OUTPUT",
                "node_version": 1,
                "parameters": {},
            },
        ],
        "connections": [
            {
                "from_node": "doc_1",
                "from_output": "documents",
                "to_node": "split_1",
                "to_input": "documents",
            },
            {
                "from_node": "split_1",
                "from_output": "chunks",
                "to_node": "merge_1",
                "to_input": "chunks",
            },
            {
                "from_node": "merge_1",
                "from_output": "chunks",
                "to_node": "save_1",
                "to_input": "chunks",
            },
            {
                "from_node": "save_1",
                "from_output": "artifact",
                "to_node": "output_1",
                "to_input": "value",
            },
        ],
        "metadata": {},
    }

###############################################################################
def test_execute_fragmentation_pipeline_returns_serialization_artifact(
    client: TestClient,
    tmp_path: Path,
    wait_for_job,
) -> None:
    source = tmp_path / "fragment-source.txt"
    source.write_text(
        "Apples are crisp. Bananas are softer. Carrots are crunchy.", encoding="utf-8"
    )
    export_target = tmp_path / "exports" / "fragments"

    compile_response = client.post(
        "/executions/compile",
        json={
            "definition": build_fragmentation_definition(
                str(source), str(export_target)
            )
        },
    )
    assert compile_response.status_code == 200
    payload = compile_response.json()
    assert payload["valid"] is True

    start_response = client.post(
        "/executions", json={"workflow_id": None, "plan": payload["plan"]}
    )
    assert start_response.status_code == 202
    run_id = start_response.json()["run_id"]

    final_status = wait_for_job(str(run_id), 3.0)
    run_payload = client.get(f"/executions/{run_id}").json()

    assert final_status["status"] == "completed"
    artifact = run_payload["outputs"]["output_1"]["json"]
    assert artifact["extension"] == ".md"
    assert artifact["count"] >= 1

    written_files = [Path(path) for path in artifact["files"]]
    assert all(path.exists() for path in written_files)
    assert all(path.suffix == ".md" for path in written_files)
    assert all(path.name.startswith("fragments_") for path in written_files)
    assert any(
        "Apples are crisp" in path.read_text(encoding="utf-8") for path in written_files
    )

# Workflow routes

###############################################################################
def build_simple_definition(prompt_text: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": prompt_text},
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
                "from_node": "prompt_1",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "text",
            },
        ],
        "metadata": {},
    }

###############################################################################
def build_provider_chat_definition() -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "system_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Follow the rules"},
            },
            {
                "node_id": "user_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Say hello"},
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
                "parameters": {
                    "context_window": 0,
                    "max_tokens": 64,
                    "use_reasoning": False,
                },
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

###############################################################################
def build_provider_structured_definition(schema: object) -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "user_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Return a person record"},
            },
            {
                "node_id": "provider_1",
                "node_type": "MODEL_PROVIDER",
                "node_version": 1,
                "parameters": {"provider": "ollama", "model_name": "llama3.2"},
            },
            {
                "node_id": "structured_1",
                "node_type": "LLM_STRUCTURED",
                "node_version": 1,
                "parameters": {
                    "context_window": 0,
                    "max_tokens": 64,
                    "use_reasoning": False,
                    "response_schema": schema,
                },
            },
        ],
        "connections": [
            {
                "from_node": "provider_1",
                "connection_type": "controller",
                "from_controller": "model",
                "to_node": "structured_1",
                "to_controller": "model",
            },
            {
                "from_node": "user_1",
                "from_output": "text",
                "to_node": "structured_1",
                "to_input": "user_prompt",
            },
        ],
        "metadata": {},
    }

###############################################################################
def build_provider_structured_with_json_output_definition(
    schema: object,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "user_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Return a person record"},
            },
            {
                "node_id": "provider_1",
                "node_type": "MODEL_PROVIDER",
                "node_version": 1,
                "parameters": {"provider": "ollama", "model_name": "llama3.2"},
            },
            {
                "node_id": "structured_1",
                "node_type": "LLM_STRUCTURED",
                "node_version": 1,
                "parameters": {
                    "context_window": 0,
                    "max_tokens": 64,
                    "use_reasoning": False,
                    "response_schema": schema,
                },
            },
            {
                "node_id": "output_1",
                "node_type": "JSON_OUTPUT",
                "node_version": 1,
                "parameters": {},
            },
        ],
        "connections": [
            {
                "from_node": "provider_1",
                "connection_type": "controller",
                "from_controller": "model",
                "to_node": "structured_1",
                "to_controller": "model",
            },
            {
                "from_node": "user_1",
                "from_output": "text",
                "to_node": "structured_1",
                "to_input": "user_prompt",
            },
            {
                "from_node": "structured_1",
                "from_output": "result",
                "to_node": "output_1",
                "to_input": "value",
            },
        ],
        "metadata": {},
    }

###############################################################################
def test_compile_returns_plan_for_prompt_graph(client: TestClient) -> None:
    response = client.post(
        "/executions/compile", json={"definition": build_simple_definition("Plan me")}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["plan"]["step_order"] == ["prompt_1", "output_1"]
    assert payload["plan"]["steps"][0]["node_type"] == "PROMPT"

###############################################################################
def test_compile_rejects_cycles(client: TestClient) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "if_1",
                        "node_type": "IF",
                        "node_version": 1,
                        "parameters": {},
                    },
                    {
                        "node_id": "router_1",
                        "node_type": "ROUTER",
                        "node_version": 1,
                        "parameters": {},
                    },
                ],
                "connections": [
                    {
                        "from_node": "if_1",
                        "from_output": "result",
                        "to_node": "router_1",
                        "to_input": "value",
                    },
                    {
                        "from_node": "router_1",
                        "from_output": "matched",
                        "to_node": "if_1",
                        "to_input": "true_value",
                    },
                ],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(item["code"] == "graph_cycle" for item in payload["diagnostics"])

###############################################################################
def test_compile_rejects_invalid_structured_schema(client: TestClient) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": build_provider_structured_definition(
                {"type": "object", "pattern": "x"}
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(
        item["code"] == "invalid_response_schema" for item in payload["diagnostics"]
    )

###############################################################################
def test_compile_rejects_llm_without_model_controller(client: TestClient) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "user_1",
                        "node_type": "PROMPT",
                        "node_version": 1,
                        "parameters": {"prompt_text": "Say hello"},
                    },
                    {
                        "node_id": "chat_1",
                        "node_type": "LLM_CHAT",
                        "node_version": 1,
                        "parameters": {
                            "context_window": 0,
                            "max_tokens": 64,
                            "use_reasoning": False,
                        },
                    },
                ],
                "connections": [
                    {
                        "from_node": "user_1",
                        "from_output": "text",
                        "to_node": "chat_1",
                        "to_input": "user_prompt",
                    },
                ],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    codes = {item["code"] for item in payload["diagnostics"]}
    assert "missing_required_controller" in codes or "missing_model_selection" in codes

###############################################################################
def test_compile_excludes_skipped_nodes_from_plan(client: TestClient) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "prompt_1",
                        "node_type": "PROMPT",
                        "node_version": 1,
                        "parameters": {"prompt_text": "Use me"},
                    },
                    {
                        "node_id": "prompt_2",
                        "node_type": "PROMPT",
                        "node_version": 1,
                        "parameters": {"prompt_text": "Skip me"},
                        "skipped": True,
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
                        "from_node": "prompt_1",
                        "from_output": "text",
                        "to_node": "output_1",
                        "to_input": "text",
                    },
                ],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["plan"]["step_order"] == ["prompt_1", "output_1"]
    assert "prompt_2" not in payload["plan"]["step_order"]
    assert payload["plan"]["metadata"]["skipped_node_ids"] == ["prompt_2"]

###############################################################################
def test_compile_skipped_connection_is_excluded_from_required_input_resolution(
    client: TestClient,
) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "prompt_1",
                        "node_type": "PROMPT",
                        "node_version": 1,
                        "parameters": {"prompt_text": "Skip source"},
                        "skipped": True,
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
                        "from_node": "prompt_1",
                        "from_output": "text",
                        "to_node": "output_1",
                        "to_input": "text",
                    },
                ],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    codes = {item["code"] for item in payload["diagnostics"]}
    assert "missing_required_input" in codes
    assert "missing_source_node" not in codes

###############################################################################
def test_compile_requires_explicit_controller_edge_even_with_global_metadata(
    client: TestClient,
) -> None:
    definition = build_provider_chat_definition()
    definition["metadata"] = {
        "global_nodes": {
            "model_provider": "provider_1",
        }
    }
    definition["connections"] = [
        connection
        for connection in definition["connections"]
        if connection.get("connection_type") != "controller"
    ]

    response = client.post("/executions/compile", json={"definition": definition})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(
        item["code"] == "missing_required_controller" for item in payload["diagnostics"]
    )
    assert any(
        item["code"] == "unsupported_global_connector_metadata"
        for item in payload["diagnostics"]
    )

###############################################################################
@pytest.mark.parametrize(
    "unsupported_node_type",
    ["USER_PROMPT", "SYSTEM_PROMPT", "EMBEDDING_MODEL", "LANCE_DB"],
)
def test_compile_rejects_removed_node_type_aliases(
    client: TestClient, unsupported_node_type: str
) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "removed_1",
                        "node_type": unsupported_node_type,
                        "node_version": 1,
                        "parameters": {},
                    }
                ],
                "connections": [],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(
        item["code"] == "unknown_node_type" and unsupported_node_type in item["message"]
        for item in payload["diagnostics"]
    )

###############################################################################
@pytest.mark.parametrize("unsupported_provider", ["anthropic", "local"])
def test_compile_rejects_removed_provider_aliases(
    client: TestClient, unsupported_provider: str
) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "provider_1",
                        "node_type": "MODEL_PROVIDER",
                        "node_version": 1,
                        "parameters": {
                            "provider": unsupported_provider,
                            "model_name": "removed-model",
                        },
                    }
                ],
                "connections": [],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(
        item["code"] == "invalid_parameter"
        and "ollama, openai, gemini, claude, deepseek, huggingface, lmstudio, llama"
        for item in payload["diagnostics"]
    )

###############################################################################
def build_huggingface_chat_definition(model_name: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "user_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Say hello"},
            },
            {
                "node_id": "provider_1",
                "node_type": "MODEL_PROVIDER",
                "node_version": 1,
                "parameters": {"provider": "huggingface", "model_name": model_name},
            },
            {
                "node_id": "chat_1",
                "node_type": "LLM_CHAT",
                "node_version": 1,
                "parameters": {
                    "context_window": 0,
                    "max_tokens": 64,
                    "use_reasoning": False,
                },
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
        ],
        "metadata": {},
    }

###############################################################################
def test_compile_allows_tokenless_local_huggingface_model(
    client: TestClient, monkeypatch
) -> None:
    model_name = "acme/local-model"
    monkeypatch.setattr(
        provider_service,
        "_downloaded_huggingface_repo_ids",
        lambda: {model_name},
    )
    monkeypatch.setattr(
        provider_service,
        "_get_provider_configuration",
        lambda provider, session_name="default": None,
    )

    response = client.post(
        "/executions/compile",
        json={"definition": build_huggingface_chat_definition(model_name)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True

###############################################################################
def test_compile_rejects_remote_huggingface_model_without_token(
    client: TestClient, monkeypatch
) -> None:
    model_name = "acme/remote-model"
    monkeypatch.setattr(
        provider_service, "_downloaded_huggingface_repo_ids", lambda: set()
    )
    monkeypatch.setattr(
        provider_service,
        "_get_provider_configuration",
        lambda provider, session_name="default": None,
    )

    response = client.post(
        "/executions/compile",
        json={"definition": build_huggingface_chat_definition(model_name)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(
        item["code"] == "provider_capability_error"
        and "requires an API key" in item["message"]
        and "remote models" in item["message"]
        for item in payload["diagnostics"]
    )

###############################################################################
def test_compile_allows_remote_huggingface_model_with_token(
    client: TestClient, monkeypatch
) -> None:
    model_name = "acme/remote-model"
    monkeypatch.setattr(
        provider_service, "_downloaded_huggingface_repo_ids", lambda: set()
    )
    monkeypatch.setattr(
        provider_service,
        "_get_provider_configuration",
        lambda provider, session_name="default": ProviderConfiguration(
            provider="huggingface", api_key="hf_test", base_url=None, metadata={}
        ),
    )

    response = client.post(
        "/executions/compile",
        json={"definition": build_huggingface_chat_definition(model_name)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True

###############################################################################
def build_stub_model_definition(
    provider: str, model: str, timeout_s: float | None = None
) -> ProviderModelDefinition:
    return ProviderModelDefinition(
        provider=provider,
        model=model,
        label=model,
        supports_image=False,
        supports_reasoning=True,
        supports_structured_output=True,
        timeout_s=timeout_s,
    )

###############################################################################
def test_execute_returns_run_and_persists_output_payload(
    client: TestClient,
    monkeypatch,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        provider_service,
        "_ollama_models",
        lambda session_name="default": (
            ModelMetadata(provider="ollama", model="llama3.2", label="llama3.2"),
        ),
    )

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return "Hello back"

    monkeypatch.setattr(provider_service, "chat", fake_chat)
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(
        provider_service,
        "build_model_definition",
        lambda provider, model, timeout_s=None, session_name="default": (
            build_stub_model_definition(provider, model, timeout_s=timeout_s)
        ),
    )

    compile_response = client.post(
        "/executions/compile", json={"definition": build_provider_chat_definition()}
    )
    plan = compile_response.json()["plan"]

    start_response = client.post(
        "/executions", json={"workflow_id": None, "plan": plan}
    )

    assert start_response.status_code == 202
    run_id = start_response.json()["run_id"]

    final_status = wait_for_job(str(run_id))
    status_response = client.get(f"/executions/{run_id}")

    assert final_status["status"] == "completed"
    assert final_status["result"] == {"outputs": {"output_1": {"text": "Hello back"}}}
    assert status_response.status_code == 200
    assert status_response.json()["outputs"] == {"output_1": {"text": "Hello back"}}
    assert captured["provider"] == "ollama"
    assert captured["model"] == "llama3.2"
    assert captured["timeout_s"] == 120
    assert captured["messages"] == [
        {"role": "system", "content": "Follow the rules"},
        {"role": "user", "content": "Say hello"},
    ]

###############################################################################
def test_execute_structured_node_rejects_invalid_output(
    client: TestClient,
    monkeypatch,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    monkeypatch.setattr(
        provider_service,
        "_ollama_models",
        lambda session_name="default": (
            ModelMetadata(provider="ollama", model="llama3.2", label="llama3.2"),
        ),
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: '{"name": 12}')
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(
        provider_service,
        "build_model_definition",
        lambda provider, model, timeout_s=None, session_name="default": (
            build_stub_model_definition(provider, model, timeout_s=timeout_s)
        ),
    )

    compile_response = client.post(
        "/executions/compile",
        json={
            "definition": build_provider_structured_definition(
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
        },
    )
    plan = compile_response.json()["plan"]

    start_response = client.post(
        "/executions", json={"workflow_id": None, "plan": plan}
    )
    run_id = start_response.json()["run_id"]

    final_status = wait_for_job(str(run_id))
    run_payload = client.get(f"/executions/{run_id}").json()

    assert final_status["status"] == "failed"
    assert "must be a string" in str(final_status["error"])
    assert run_payload["steps"][2]["status"] == "failed"

###############################################################################
def test_execute_structured_node_emits_json_output_payload(
    client: TestClient,
    monkeypatch,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    monkeypatch.setattr(
        provider_service,
        "_ollama_models",
        lambda session_name="default": (
            ModelMetadata(provider="ollama", model="llama3.2", label="llama3.2"),
        ),
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: '{"name":"Ada"}')
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(
        provider_service,
        "build_model_definition",
        lambda provider, model, timeout_s=None, session_name="default": (
            build_stub_model_definition(provider, model, timeout_s=timeout_s)
        ),
    )

    compile_response = client.post(
        "/executions/compile",
        json={
            "definition": build_provider_structured_with_json_output_definition(
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
        },
    )
    plan = compile_response.json()["plan"]

    start_response = client.post(
        "/executions", json={"workflow_id": None, "plan": plan}
    )
    run_id = start_response.json()["run_id"]

    final_status = wait_for_job(str(run_id))
    run_payload = client.get(f"/executions/{run_id}").json()

    assert final_status["status"] == "completed"
    assert final_status["result"] == {
        "outputs": {"output_1": {"json": {"name": "Ada"}, "name": "Ada"}}
    }
    assert run_payload["outputs"] == {
        "output_1": {"json": {"name": "Ada"}, "name": "Ada"}
    }

# Workflow template routes

###############################################################################
def test_list_workflow_templates_returns_expected_templates(client: TestClient) -> None:
    response = client.get("/workflow-templates")

    assert response.status_code == 200
    payload = response.json()
    assert "templates" in payload
    template_ids = {item["id"] for item in payload["templates"]}
    assert template_ids == {
        "system_user_llm_structured_output_v1",
        "system_user_llm_chat_output_v1",
        "load_documents_chunk_embed_store_v1",
    }
