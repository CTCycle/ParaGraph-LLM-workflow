from __future__ import annotations

from fastapi.testclient import TestClient

###############################################################################
def test_list_workflow_templates_returns_expected_templates(client: TestClient) -> None:
    response = client.get("/workflows/templates")

    assert response.status_code == 200
    payload = response.json()
    assert "templates" in payload
    template_ids = {item["id"] for item in payload["templates"]}
    assert template_ids == {
        "system_user_llm_structured_output_v1",
        "system_user_llm_chat_output_v1",
        "load_documents_chunk_embed_store_v1",
    }
