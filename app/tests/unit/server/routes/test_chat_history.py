from __future__ import annotations

from fastapi.testclient import TestClient


def _handle(node_id: str = "chat-node") -> dict[str, object]:
    return {
        "node_type": "CHAT_HISTORY_MEMORY",
        "node_id": node_id,
        "workflow_id": "api-workflow",
        "execution_session_id": "api-session",
        "max_messages": 10,
        "separator": "\n",
        "keep_prompt_type": True,
        "execution_owned": True,
    }


def test_chat_history_route_reads_and_resets_a_single_scope(
    client: TestClient,
) -> None:
    from server.repositories.workflow import in_memory_chat_history_repository
    from server.contracts.chat_history import ChatHistoryMessage

    in_memory_chat_history_repository.append_messages(
        "api-workflow",
        "api-session",
        "chat-node",
        [ChatHistoryMessage(role="user", content="hello")],
    )

    response = client.get(
        "/chat-history",
        params={**_handle(), "node_type": "CHAT_HISTORY_MEMORY"},
    )
    assert response.status_code == 200
    assert response.json()["messages"][0]["content"] == "hello"

    reset = client.post("/chat-history/reset", json=_handle())
    assert reset.status_code == 200
    assert reset.json() == {"messages": []}

    after_reset = client.get(
        "/chat-history",
        params={**_handle(), "node_type": "CHAT_HISTORY_MEMORY"},
    )
    assert after_reset.json() == {"messages": []}
