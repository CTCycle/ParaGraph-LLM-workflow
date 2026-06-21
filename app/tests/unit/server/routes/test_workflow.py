from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
import pytest

from server.domain.configuration import AccessKeyConfiguration
from server.domain.node_catalog import ProviderModelDefinition
from server.services.workflow import provider_service


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
def test_compile_ignores_unknown_global_node_aliases(client: TestClient) -> None:
    definition = build_provider_chat_definition()
    definition["metadata"] = {
        "global_nodes": {
            "model": "provider_1",
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
        "_get_access_key",
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
        "_get_access_key",
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
        and "requires an access key" in item["message"]
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
        "_get_access_key",
        lambda provider, session_name="default": AccessKeyConfiguration(
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
