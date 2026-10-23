from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap
from server.common import path as common_path
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from server.api.client_hosting import ClientHostingMiddleware
import ast

# CORS policy

_CORS_PROBE = textwrap.dedent(
    """
    import os
    from pathlib import Path

    from fastapi.testclient import TestClient

    from server.configurations.environment import EnvironmentLoader
    from server.configurations.startup import get_configuration_runtime

    get_configuration_runtime()._environment_loader = EnvironmentLoader(
        Path(os.environ["PARAGRAPH_CORS_TEST_ENV"])
    )

    from server.app import create_app

    client = TestClient(create_app())
    mode = os.environ["PARAGRAPH_CORS_TEST_MODE"]

    if mode == "disabled":
        response = client.get(
            "/docs", headers={"Origin": "https://ui.example"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers
    elif mode == "defaults":
        allowed_preflight = client.options(
            "/configurations",
            headers={
                "Origin": "https://ui.example",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert allowed_preflight.status_code == 200
        assert allowed_preflight.headers["access-control-allow-origin"] == (
            "https://ui.example"
        )
        assert "access-control-allow-credentials" not in allowed_preflight.headers
        assert "PUT" in allowed_preflight.headers[
            "access-control-allow-methods"
        ]
        allowed_headers = allowed_preflight.headers[
            "access-control-allow-headers"
        ].lower()
        assert "authorization" in allowed_headers
        assert "content-type" in allowed_headers

        rejected_method = client.options(
            "/configurations",
            headers={
                "Origin": "https://ui.example",
                "Access-Control-Request-Method": "TRACE",
            },
        )
        assert rejected_method.status_code == 400
    else:
        allowed_preflight = client.options(
            "/configurations",
            headers={
                "Origin": "https://ui.example",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert allowed_preflight.status_code == 200
        assert allowed_preflight.headers["access-control-allow-origin"] == (
            "https://ui.example"
        )
        assert allowed_preflight.headers["access-control-allow-credentials"] == "true"
        assert "PUT" in allowed_preflight.headers[
            "access-control-allow-methods"
        ]
        allowed_headers = allowed_preflight.headers[
            "access-control-allow-headers"
        ].lower()
        assert "authorization" in allowed_headers
        assert "content-type" in allowed_headers

        allowed_request = client.get(
            "/docs", headers={"Origin": "https://ui.example"}
        )
        assert allowed_request.status_code == 200
        assert allowed_request.headers["access-control-allow-origin"] == (
            "https://ui.example"
        )

        rejected_preflight = client.options(
            "/configurations",
            headers={
                "Origin": "https://other.example",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert rejected_preflight.status_code == 400
        assert "access-control-allow-origin" not in rejected_preflight.headers
    """
)

def _run_cors_probe(tmp_path: Path, *, mode: str, env_text: str) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(env_text, encoding="utf-8")

    repository_root = Path(__file__).resolve().parents[4]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository_root / "app")
    environment["PARAGRAPH_CORS_TEST_ENV"] = str(env_path)
    environment["PARAGRAPH_CORS_TEST_MODE"] = mode

    result = subprocess.run(
        [sys.executable, "-c", _CORS_PROBE],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout

def test_cors_is_disabled_when_no_origins_are_configured(tmp_path: Path) -> None:
    _run_cors_probe(
        tmp_path,
        mode="disabled",
        env_text="CORS_ALLOWED_ORIGINS=\n",
    )

def test_cors_uses_documented_allow_lists_and_credentials_default(
    tmp_path: Path,
) -> None:
    _run_cors_probe(
        tmp_path,
        mode="defaults",
        env_text=(
            "CORS_ALLOWED_ORIGINS=https://ui.example\n"
            "CORS_ALLOW_CREDENTIALS=false\n"
            "CORS_ALLOWED_METHODS=GET,POST,PUT,PATCH,DELETE,OPTIONS\n"
            "CORS_ALLOWED_HEADERS=Authorization,Content-Type\n"
        ),
    )

def test_cors_allows_configured_origin_and_rejects_other_origins(
    tmp_path: Path,
) -> None:
    _run_cors_probe(
        tmp_path,
        mode="configured",
        env_text=(
            "CORS_ALLOWED_ORIGINS=https://ui.example\n"
            "CORS_ALLOW_CREDENTIALS=true\n"
            "CORS_ALLOWED_METHODS=GET,PUT,OPTIONS\n"
            "CORS_ALLOWED_HEADERS=Authorization,Content-Type\n"
        ),
    )

# Cache placement

###############################################################################
def test_application_cache_root_is_repository_canonical() -> None:
    expected_root = Path(__file__).resolve().parents[4] / "runtimes" / "cache"

    assert common_path.CACHE_ROOT == expected_root
    assert common_path.FRONTEND_DIST_ROOT == expected_root / "frontend-dist"
    assert sys.pycache_prefix == str(expected_root / "pycache")

###############################################################################
def test_library_cache_environment_is_repository_canonical() -> None:
    expected_root = common_path.CACHE_ROOT

    assert os.environ["PYTHONPYCACHEPREFIX"] == str(expected_root / "pycache")
    assert os.environ["HF_HOME"] == str(expected_root / "huggingface")
    assert os.environ["HF_HUB_CACHE"] == str(expected_root / "huggingface" / "hub")
    assert os.environ["HF_ASSETS_CACHE"] == str(
        expected_root / "huggingface" / "assets"
    )
    assert os.environ["HF_XET_CACHE"] == str(expected_root / "huggingface" / "xet")
    assert os.environ["TORCH_HOME"] == str(expected_root / "torch")

# Client hosting

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

# Contract boundaries

FORBIDDEN_IMPORT_PREFIXES = (
    "fastapi",
    "server.api",
    "server.repositories",
    "server.services",
    "sqlalchemy",
)

###############################################################################
def test_contract_modules_remain_transport_and_persistence_neutral() -> None:
    contract_root = Path(__file__).resolve().parents[3] / "server" / "contracts"

    for path in sorted(contract_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported_modules = [node.module or ""]
            else:
                continue

            for module in imported_modules:
                assert not any(
                    module == prefix or module.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_IMPORT_PREFIXES
                ), f"{path} imports forbidden runtime module {module}"

# Generated frontend contracts

###############################################################################
def test_generated_frontend_api_contracts_match_fastapi_openapi() -> None:
    root = Path(__file__).resolve().parents[4]
    generator = root / "app/scripts/generate_frontend_api_contracts.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "app")

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
