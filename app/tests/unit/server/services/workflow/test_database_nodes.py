from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from server.services.workflow import node_registry
from server.repositories.workflow.database import inspect_database_schema

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


def test_database_query_nodes_keep_one_typed_controller_contract() -> None:
    expected = ("CRUD_READ", "CUSTOM_SQL_QUERY")

    for node_type in expected:
        manifest = node_registry.get(node_type, 1)
        assert manifest is not None
        assert len(manifest.controllers) == 1
        assert manifest.controllers[0].name == "connection"
        assert manifest.controllers[0].data_type == "DATABASE_CONNECTION"


def test_database_parameters_reject_unknown_fields() -> None:
    with pytest.raises(ValueError, match="password"):
        node_registry.validate_parameters(
            "CUSTOM_SQL_QUERY",
            1,
            {"sql": "select 1", "password": "must-not-be-accepted"},
        )
