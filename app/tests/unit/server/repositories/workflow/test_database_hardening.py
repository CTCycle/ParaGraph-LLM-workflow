from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from server.repositories.workflow import database as database_repository
from server.repositories.workflow.database import (
    build_database_url,
    engine_registry,
    execute_bulk_create,
    execute_create,
    execute_custom_sql,
    execute_read,
    execute_update,
    execute_upsert,
    register_database_credential,
    reset_database_engines,
)

###############################################################################
def _connection(path: Path, *, read_only: bool = False) -> dict[str, object]:
    return {
    "engine": "sqlite",
    "file_path": str(path),
    "read_only": read_only,
        "database_name": None,
        "host": None,
        "port": None,
        "username": None,
        "credential_ref": None,
        "options": {},
    }

###############################################################################
def test_postgresql_workflow_connection_contract_keeps_psycopg_driver() -> None:
    url, connect_args = build_database_url(
        {
            "engine": "postgres",
            "database_name": "workflow_db",
            "host": "db.example.test",
            "port": 5432,
            "username": "workflow_user",
            "credential_ref": register_database_credential("secret"),
            "options": {"sslmode": "require", "connect_timeout_s": 9},
        }
    )

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "workflow_db"
    assert url.host == "db.example.test"
    assert connect_args == {"connect_timeout": 9}


###############################################################################
def test_database_url_rejects_inline_passwords() -> None:
    with pytest.raises(ValueError, match="opaque credential_ref"):
        build_database_url(
            {
                "engine": "postgres",
                "database_name": "workflow_db",
                "host": "db.example.test",
                "port": 5432,
                "username": "workflow_user",
                "password": "secret",
            }
        )

###############################################################################
def test_postgresql_upsert_dialect_contract() -> None:
    table = Table(
        "items",
        MetaData(),
        Column("name", String, primary_key=True),
        Column("value", Integer),
    )
    statement = (
        postgresql_insert(table)
        .values(name="one", value=1)
        .on_conflict_do_update(index_elements=["name"], set_={"value": 2})
    )

    assert "ON CONFLICT" in str(statement.compile(dialect=postgresql_dialect()))

###############################################################################
@pytest.fixture
def database(tmp_path: Path):
    path = tmp_path / "hardening.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "create table items (id integer primary key autoincrement, name text unique not null, value integer, version integer not null default 1)"
            )
        )
    engine.dispose()
    yield path
    reset_database_engines()

###############################################################################
def test_engine_reuse_disposal_and_credential_safe_identity(database: Path) -> None:
    reset_database_engines()
    connection = _connection(database)
    first = engine_registry.get(connection)
    second = engine_registry.get(connection)
    assert first is second
    assert engine_registry.size() == 1
    assert "secret" not in engine_registry.identity(connection)
    reset_database_engines()
    assert engine_registry.size() == 0

###############################################################################
def test_read_only_enforcement_and_parameterized_single_statement_sql(
    database: Path,
) -> None:
    writable = _connection(database)
    readonly = _connection(database, read_only=True)
    execute_create(writable, table_name="items", values={"name": "Ada", "value": None})

    with pytest.raises(ValueError, match="READ_ONLY_VIOLATION"):
        execute_create(readonly, table_name="items", values={"name": "Grace"})
    rows = execute_custom_sql(
        readonly,
        sql="select name from items where name = :name",
        parameters={"name": "Ada"},
        read_only=True,
    )
    assert rows["rows"] == [{"name": "Ada"}]
    with pytest.raises(ValueError, match="MULTIPLE_STATEMENTS"):
        execute_custom_sql(writable, sql="select 1; select 2")
    with pytest.raises(ValueError, match="READ_ONLY_SQL_REQUIRED"):
        execute_custom_sql(writable, sql="delete from items", read_only=True)
    with pytest.raises(ValueError, match="READ_ONLY_VIOLATION"):
        execute_custom_sql(readonly, sql="delete from items", read_only=False)


###############################################################################
def test_mysql_upsert_is_rejected_before_table_access(monkeypatch) -> None:

    ###############################################################################
    class FakeDialect:
        name = "mysql"

    ###############################################################################
    class FakeEngine:
        dialect = FakeDialect()

    monkeypatch.setattr(
        database_repository,
        "build_engine_from_connection",
        lambda connection: FakeEngine(),
    )

    def unexpected_table_load(*args, **kwargs):
        raise AssertionError("unsupported upsert should fail before table access")

    monkeypatch.setattr(database_repository, "_load_table", unexpected_table_load)

    with pytest.raises(ValueError, match="UPSERT_UNSUPPORTED: mysql"):
        execute_upsert(
            _connection(Path("unused.sqlite")),
            table_name="items",
            conflict_columns=["name"],
            insert_values={"name": "Ada"},
            update_values={"value": 1},
        )

###############################################################################
def test_generated_ids_pagination_upsert_and_optimistic_concurrency(
    database: Path,
) -> None:
    connection = _connection(database)
    created = execute_create(
        connection, table_name="items", values={"name": "one", "value": 1}
    )
    assert created["generated_identifiers"] == [1]
    execute_create(connection, table_name="items", values={"name": "two", "value": 2})
    page = execute_read(
        connection,
        table_name="items",
        columns=[],
        filters={},
        limit=1,
        offset=1,
        order_by="",
    )
    assert page["rows"][0]["name"] == "two"
    assert page["pagination"] == {
        "limit": 1,
        "offset": 1,
        "total_count": 2,
        "has_more": False,
    }

    execute_upsert(
        connection,
        table_name="items",
        conflict_columns=["name"],
        insert_values={"name": "one", "value": 9},
        update_values={"value": 9},
    )
    conflict = execute_update(
        connection,
        table_name="items",
        values={"value": 3},
        filters={"name": "one"},
        version_column="version",
        expected_version=99,
        increment_version=True,
    )
    assert conflict["affected_rows"] == 0

###############################################################################
def test_bulk_create_rolls_back_entire_batch_on_constraint_failure(
    database: Path,
) -> None:
    connection = _connection(database)
    with pytest.raises(ValueError, match="Bulk create operation failed"):
        execute_bulk_create(
            connection,
            table_name="items",
            values=[
                {"name": "duplicate", "value": 1},
                {"name": "duplicate", "value": 2},
            ],
        )
    result = execute_read(
        connection,
        table_name="items",
        columns=[],
        filters={},
        limit=10,
        offset=0,
        order_by="",
    )
    assert result["rows"] == []
