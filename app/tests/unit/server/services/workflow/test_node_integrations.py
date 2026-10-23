from __future__ import annotations

from pathlib import Path
import pytest
from sqlalchemy import ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from server.services.workflow import node_registry
from server.repositories.workflow.database import inspect_database_schema
from datetime import UTC, datetime, timedelta
import httpx
from server.contracts.node_handler_http import HttpRequestParameters
from server.services.workflow.http_transport import HttpTransportError, SecureHttpTransport
from server.common import path as common_path
from server.services.workflow.node_handlers import http as http_nodes_module
import json
from server.repositories.workflow.node_manifest import NodeManifestRepository
from server.services.workflow.nodes import registry as node_module

# Database nodes

###############################################################################
class DatabaseBase(DeclarativeBase):
    pass

###############################################################################
class User(DatabaseBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")

###############################################################################
class Post(DatabaseBase):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)

###############################################################################
def _database_connection(tmp_path: Path) -> dict[str, object]:
    database_path = tmp_path / "crud.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    DatabaseBase.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(User(name="Ada", status="active"))
        db_session.commit()
    engine.dispose()

    payload = node_registry.execute(
        "SQL_FILE_DATABASE",
        1,
        {"db_path": str(database_path), "db_connect_timeout": 30},
        {},
    )
    return payload["connection"]

###############################################################################
def test_database_schema_inspection_reports_tables_columns_and_foreign_keys(
    tmp_path: Path,
) -> None:
    connection = _database_connection(tmp_path)
    schema = inspect_database_schema(connection)

    tables = {table["name"]: table for table in schema["tables"]}
    assert {"users", "posts"} <= set(tables)
    assert any(
        column["name"] == "id" and column["primary_key"]
        for column in tables["users"]["columns"]
    )
    assert tables["posts"]["foreign_keys"][0]["referred_table"] == "users"

###############################################################################
def test_crud_nodes_create_read_update_and_delete_rows(tmp_path: Path) -> None:
    connection = _database_connection(tmp_path)

    created = node_registry.execute(
        "CRUD_CREATE",
        1,
        {"table": "users", "values": {"name": "Grace", "status": "active"}},
        {},
        {"connection": connection},
    )
    assert created["dataset"]["affected_rows"] == 1

    read = node_registry.execute(
        "CRUD_READ",
        1,
        {
            "table": "users",
            "columns": "id,name,status",
            "filters": {"name": "Grace"},
            "limit": 10,
            "order_by": "id",
        },
        {},
        {"connection": connection},
    )
    assert read["dataset"]["columns"] == ["id", "name", "status"]
    assert read["dataset"]["rows"][0]["name"] == "Grace"

    updated = node_registry.execute(
        "CRUD_UPDATE",
        1,
        {
            "table": "users",
            "values": {"status": "inactive"},
            "filters": {"name": "Grace"},
        },
        {},
        {"connection": connection},
    )
    assert updated["dataset"]["affected_rows"] == 1

    deleted = node_registry.execute(
        "CRUD_DELETE",
        1,
        {"table": "users", "filters": {"name": "Grace"}},
        {},
        {"connection": connection},
    )
    assert deleted["dataset"]["affected_rows"] == 1

###############################################################################
def test_crud_update_and_delete_require_filters(tmp_path: Path) -> None:
    connection = _database_connection(tmp_path)

    for node_type, parameters in [
        (
            "CRUD_UPDATE",
            {"table": "users", "values": {"status": "inactive"}, "filters": {}},
        ),
        ("CRUD_DELETE", {"table": "users", "filters": {}}),
    ]:
        try:
            node_registry.execute(
                node_type, 1, parameters, {}, {"connection": connection}
            )
        except ValueError as exc:
            assert "filters are required" in str(exc)
        else:
            raise AssertionError(f"Expected {node_type} to reject empty filters")

###############################################################################
def test_custom_sql_query_returns_rows_and_rejects_invalid_sql(tmp_path: Path) -> None:
    connection = _database_connection(tmp_path)

    payload = node_registry.execute(
        "CUSTOM_SQL_QUERY",
        1,
        {"sql": "select name from users where status = 'active'"},
        {},
        {"connection": connection},
    )
    assert payload["dataset"]["columns"] == ["name"]
    assert payload["dataset"]["rows"] == [{"name": "Ada"}]

    for sql in ["", "select 1; select 2"]:
        try:
            node_registry.execute(
                "CUSTOM_SQL_QUERY", 1, {"sql": sql}, {}, {"connection": connection}
            )
        except ValueError as exc:
            assert "sql" in str(exc)
        else:
            raise AssertionError("Expected invalid SQL to fail validation")

###############################################################################
def test_database_query_nodes_keep_one_typed_controller_contract() -> None:
    expected = ("CRUD_READ", "CUSTOM_SQL_QUERY")

    for node_type in expected:
        manifest = node_registry.get(node_type, 1)
        assert manifest is not None
        assert len(manifest.controllers) == 1
        assert manifest.controllers[0].name == "connection"
        assert manifest.controllers[0].data_type == "DATABASE_CONNECTION"

###############################################################################
def test_database_parameters_reject_unknown_fields() -> None:
    with pytest.raises(ValueError, match="password"):
        node_registry.validate_parameters(
            "CUSTOM_SQL_QUERY",
            1,
            {"sql": "select 1", "password": "must-not-be-accepted"},
        )

# HTTP nodes

###############################################################################
def PUBLIC_RESOLVER(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]

###############################################################################
def _execute(
    handler, *, parameters=None, sleep=lambda delay: None, cancelled=lambda: False
):
    parsed = HttpRequestParameters.model_validate(
        {"url": "https://example.test/resource", **(parameters or {})}
    )
    return SecureHttpTransport(
        resolver=PUBLIC_RESOLVER,
        transport=httpx.MockTransport(handler),
        sleep=sleep,
        jitter=lambda: 0.0,
        cancelled=cancelled,
    ).execute(parsed, {})

###############################################################################
@pytest.mark.parametrize(
    "method", ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
)
def test_all_supported_methods_use_shared_transport(method: str) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200, json={"method": request.method})

    parameters = {"method": method}
    if method in {"POST", "PATCH"}:
        parameters["idempotency_key"] = "stable"
    assert _execute(handler, parameters=parameters)["json"] == {"method": method}
    assert seen == [method]

###############################################################################
@pytest.mark.parametrize(
    ("body_mode", "parameters", "expected"),
    [
        ("json", {"json_body": {"a": 1}}, b'{"a":1}'),
        ("text", {"text_body": "hello"}, b"hello"),
        ("form", {"form_body": {"a": "1"}}, b"a=1"),
        ("binary", {"text_body": "bytes"}, b"bytes"),
    ],
)
def test_request_body_modes(body_mode, parameters, expected: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == expected
        return httpx.Response(204)

    _execute(
        handler,
        parameters={
            "method": "POST",
            "idempotency_key": "stable",
            "body_mode": body_mode,
            "accepted_statuses": [204],
            **parameters,
        },
    )

###############################################################################
def test_binary_invalid_json_and_size_limit() -> None:
    result = _execute(
        lambda request: httpx.Response(200, content=b"\x00\x01"),
        parameters={"response_mode": "binary"},
    )
    assert result["binary_base64"] == "AAE="
    with pytest.raises(HttpTransportError, match="valid JSON") as invalid:
        _execute(
            lambda request: httpx.Response(200, text="not-json"),
            parameters={"response_mode": "json"},
        )
    assert invalid.value.code == "invalid_json"
    with pytest.raises(HttpTransportError) as too_large:
        _execute(
            lambda request: httpx.Response(200, content=b"12345"),
            parameters={"max_response_bytes": 4},
        )
    assert too_large.value.code == "response_too_large"

###############################################################################
def test_file_response_commits_only_an_accepted_response(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(common_path, "ARTIFACT_ROOT", tmp_path)
    destination = tmp_path / "response.bin"
    destination.write_bytes(b"last-good")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, content=b"failed-response")
        return httpx.Response(200, content=b"accepted-response")

    result = _execute(
        handler,
        parameters={
            "response_mode": "file",
            "download_path": "response.bin",
            "max_attempts": 2,
        },
        sleep=lambda delay: None,
    )

    assert result["download_path"] == str(destination)
    assert destination.read_bytes() == b"accepted-response"
    assert not list(tmp_path.glob("*.partial-*"))

###############################################################################
def test_file_request_body_is_replayed_for_status_retry(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(common_path, "ARTIFACT_ROOT", tmp_path)
    (tmp_path / "request.bin").write_bytes(b"request-payload")
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(503 if len(seen) == 1 else 200)

    _execute(
        handler,
        parameters={
            "method": "PUT",
            "body_mode": "file",
            "upload_path": "request.bin",
            "max_attempts": 2,
        },
    )

    assert seen == [b"request-payload", b"request-payload"]

###############################################################################
def test_retry_rebuilds_basic_auth_after_cross_origin_redirect(monkeypatch) -> None:
    monkeypatch.setattr(
        SecureHttpTransport,
        "_resolve_credentials",
        staticmethod(lambda parameters: ("secret", None)),
    )
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers.get("Authorization")))
        if len(seen) == 1:
            return httpx.Response(302, headers={"Location": "https://other.test/final"})
        if len(seen) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    result = _execute(
        handler,
        parameters={
            "auth_mode": "basic",
            "credential_profile": "profile",
            "username": "user",
            "max_redirects": 1,
            "max_attempts": 2,
            "retry_statuses": [503],
        },
    )

    assert result["json"] == {"ok": True}
    assert seen[0][0].startswith("https://93.184.216.34")
    assert seen[0][1].startswith("Basic ")
    assert seen[1][0].startswith("https://93.184.216.34")
    assert seen[1][1] is None
    assert seen[2][0].startswith("https://93.184.216.34")
    assert seen[2][1].startswith("Basic ")

###############################################################################
def test_retry_backoff_rechecks_cancellation() -> None:
    cancelled = False
    delays: list[float] = []

    def sleep(delay: float) -> None:
        nonlocal cancelled
        delays.append(delay)
        cancelled = True

    with pytest.raises(HttpTransportError) as error:
        _execute(
            lambda request: httpx.Response(503),
            parameters={"max_attempts": 2},
            sleep=sleep,
            cancelled=lambda: cancelled,
        )

    assert error.value.code == "cancelled"
    assert len(delays) == 1

###############################################################################
def test_retry_after_and_idempotency_key_retention() -> None:
    calls: list[str] = []
    delays: list[float] = []
    retry_date = (datetime.now(UTC) + timedelta(seconds=1)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Idempotency-Key"])
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        if len(calls) == 2:
            return httpx.Response(429, headers={"Retry-After": retry_date})
        return httpx.Response(200, json={"ok": True})

    result = _execute(
        handler,
        parameters={
            "method": "POST",
            "idempotency_key": "one-key",
            "max_attempts": 3,
            "max_retry_delay": 2,
        },
        sleep=delays.append,
    )
    assert result["json"] == {"ok": True}
    assert calls == ["one-key", "one-key", "one-key"]
    assert delays[0] == 1 and 0 <= delays[1] <= 2

###############################################################################
def test_unsafe_retry_requires_explicit_contract() -> None:
    with pytest.raises(ValueError, match="unsafe HTTP retries"):
        HttpRequestParameters(url="https://example.test", method="POST", max_attempts=2)

###############################################################################
def test_redirect_revalidation_and_loop_limit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": "https://other.test/final"})

    with pytest.raises(HttpTransportError) as limited:
        _execute(handler, parameters={"max_redirects": 1})
    assert limited.value.code == "redirect_limit"
    assert calls == 2

###############################################################################
@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1"],
)
def test_ssrf_blocks_private_metadata_and_mapped_addresses(address: str) -> None:
    transport = SecureHttpTransport(resolver=lambda host, port: [address])
    with pytest.raises(HttpTransportError) as blocked:
        transport.execute(HttpRequestParameters(url="http://target.test"), {})
    assert blocked.value.code == "ssrf_blocked"

###############################################################################
def test_credential_url_dns_rebinding_and_cancellation() -> None:
    with pytest.raises(HttpTransportError) as credentials:
        SecureHttpTransport(resolver=PUBLIC_RESOLVER).execute(
            HttpRequestParameters(url="https://user:pass@example.test"), {}
        )
    assert credentials.value.code == "credential_url"
    with pytest.raises(HttpTransportError) as rebinding:
        SecureHttpTransport(
            resolver=lambda host, port: ["93.184.216.34", "127.0.0.1"]
        ).execute(HttpRequestParameters(url="https://example.test"), {})
    assert rebinding.value.code == "ssrf_blocked"
    with pytest.raises(HttpTransportError) as cancelled:
        _execute(lambda request: httpx.Response(200), cancelled=lambda: True)
    assert cancelled.value.code == "cancelled"

###############################################################################
@pytest.mark.parametrize(
    ("node_type", "expected_method"),
    [
        ("HTTP_GET", "GET"),
        ("HTTP_POST", "POST"),
        ("HTTP_PUT", "PUT"),
        ("HTTP_PATCH", "PATCH"),
        ("HTTP_DELETE", "DELETE"),
    ],
)
def test_method_specific_http_nodes_share_the_transport_executor(
    monkeypatch, node_type: str, expected_method: str
) -> None:
    seen: list[str] = []

    ###############################################################################
    class FakeTransport:

        # -------------------------------------------------------------------------
        def __init__(self, **kwargs) -> None:
            pass

        # -------------------------------------------------------------------------
        def execute(self, parameters, inputs):
            seen.append(parameters.method)
            return {"status_code": 200, "text": "ok", "json": {"ok": True}}

    monkeypatch.setattr(http_nodes_module, "SecureHttpTransport", FakeTransport)

    result = node_registry.execute(
        node_type,
        1,
        {"url": "https://example.test"},
        {},
    )

    assert seen == [expected_method]
    assert result["response"]["status_code"] == 200

# Plugin nodes

###############################################################################
def write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

###############################################################################
def build_plugin_manifest(script_path: str) -> dict[str, object]:
    return {
        "id": "CUSTOM_SCRIPT_NODE",
        "version": 1,
        "name": "Custom Script Node",
        "category": "processing",
        "description": "Execute custom logic from a local plugin script.",
        "inputs": [
            {
                "name": "text",
                "data_type": "TEXT",
                "required": True,
                "accepts_multiple": False,
            }
        ],
        "outputs": [
            {
                "name": "result",
                "data_type": "TEXT",
                "required": True,
                "accepts_multiple": False,
            }
        ],
        "parameters": [
            {
                "name": "prefix",
                "data_type": "TEXT",
                "default": "",
                "constraints": {},
                "ui_control": "text",
                "description": "String prefix.",
            }
        ],
        "ui": {
            "default_width": 280,
            "accent_color": "#4aa3ff",
            "icon": "sparkles",
            "collapsed_by_default": False,
        },
        "runtime": {
            "executor_key": "custom.plugin",
            "cacheable": False,
            "deterministic": True,
            "side_effecting": False,
            "plugin": {
                "script_path": script_path,
                "entrypoint": "execute",
            },
        },
    }

###############################################################################
def test_plugin_node_executes_script_runtime(tmp_path: Path) -> None:
    node_root = tmp_path / "nodes"
    plugins_root = node_root / "plugins"
    plugins_root.mkdir(parents=True, exist_ok=True)

    plugin_script = plugins_root / "custom_script_node.py"
    plugin_script.write_text(
        """
def execute(parameters, inputs):
    prefix = str(parameters.get('prefix', ''))
    text = str(inputs.get('text', ''))
    return {'result': f"{prefix}{text}".upper()}
""".strip(),
        encoding="utf-8",
    )

    write_manifest(
        node_root / "custom_script_node_v1.json",
        build_plugin_manifest("plugins/custom_script_node.py"),
    )

    registry = node_module.NodeRegistry(NodeManifestRepository(node_root))

    result = registry.execute(
        "CUSTOM_SCRIPT_NODE", 1, {"prefix": "pre-"}, {"text": "hello"}
    )
    assert result == {"result": "PRE-HELLO"}

###############################################################################
def test_plugin_node_rejects_absolute_script_paths(tmp_path: Path) -> None:
    node_root = tmp_path / "nodes"
    node_root.mkdir(parents=True, exist_ok=True)
    absolute_script = (tmp_path / "absolute_plugin.py").resolve()

    write_manifest(
        node_root / "custom_script_node_v1.json",
        build_plugin_manifest(str(absolute_script)),
    )

    with pytest.raises(ValueError, match="must be relative"):
        node_module.NodeRegistry(NodeManifestRepository(node_root))
