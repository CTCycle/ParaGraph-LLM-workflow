from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from server.repositories.workflow.database import (
    engine_registry,
    execute_bulk_create,
    execute_create,
    execute_custom_sql,
    execute_read,
    execute_update,
    execute_upsert,
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
        "password": None,
        "credential_ref": None,
        "options": {},
    }

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
    assert "password" not in engine_registry.identity(
        {**connection, "password": "secret"}
    )
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
