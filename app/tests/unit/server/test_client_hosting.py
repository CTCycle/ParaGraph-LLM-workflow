from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from server.api.client_hosting import ClientHostingMiddleware

HTML = {"Accept": "text/html,application/xhtml+xml"}


###############################################################################
def build_client(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")

    api = FastAPI()

    @api.get("/nodes")
    def nodes() -> dict[str, str]:
        return {"source": "api"}

    @api.websocket("/executions/ws/runs/{run_id}")
    async def run_socket(websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        await websocket.send_text(run_id)
        await websocket.close()

    api.add_middleware(
        ClientHostingMiddleware, api_base="/api/", client_root=tmp_path
    )
    return TestClient(api)


###############################################################################
def test_api_prefix_is_stripped_for_http_and_websocket(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    assert client.get("/api/nodes", headers=HTML).json() == {"source": "api"}
    with client.websocket_connect("/api/executions/ws/runs/r1") as socket:
        assert socket.receive_text() == "r1"


###############################################################################
def test_browser_navigation_gets_spa_while_fetch_reaches_api(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)

    assert "spa" in client.get("/nodes", headers=HTML).text
    assert "spa" in client.get("/missing/route", headers=HTML).text
    assert client.get("/nodes").json() == {"source": "api"}
    assert "docs" in client.get("/docs", headers=HTML).text.lower()


###############################################################################
def test_built_files_are_served_and_traversal_falls_back_to_index(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)

    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert "spa" in client.get("/..%2f..%2fsecret", headers=HTML).text
