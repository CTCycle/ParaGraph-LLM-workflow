from __future__ import annotations

import time

from fastapi.testclient import TestClient


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


def test_get_execution_returns_404_for_unknown_run(client: TestClient) -> None:
    response = client.get("/executions/run-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found: run-missing"


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
