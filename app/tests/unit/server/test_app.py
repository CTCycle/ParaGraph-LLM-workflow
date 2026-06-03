from __future__ import annotations

import server.app as server_app_module
from fastapi.testclient import TestClient


###############################################################################
def test_root_redirects_to_docs(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


###############################################################################
def test_root_serves_client_build_in_tauri_mode(monkeypatch) -> None:
    monkeypatch.setenv("PARAGRAPH_TAURI_MODE", "true")

    app = server_app_module.create_app()
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
