from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap


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
