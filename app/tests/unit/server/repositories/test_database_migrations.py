from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

import portalocker
import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy import inspect, text

from server.common import path as common_path
from server.configurations.settings import SQLiteSettings
from server.repositories.database import migration
from server.repositories.database.initializer import initialize_sqlite_database
from server.repositories.schemas import Base, UserSession


###############################################################################
def _settings() -> SQLiteSettings:
    return SQLiteSettings(insert_batch_size=1000)


###############################################################################
def _engine(database_path: Path) -> sa.Engine:
    return sa.create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"autocommit": False},
    )


###############################################################################
def _add_legacy_node_table(engine: sa.Engine) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "user_sessions",
        metadata,
        sa.Column("session_id", sa.Integer(), primary_key=True),
    )
    nodes = sa.Table(
        "nodes",
        metadata,
        sa.Column("node_configuration_id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("user_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("node_version", sa.Integer(), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "node_key", name="uq_nodes_session_node_key"),
    )
    sa.Index("ix_nodes_session_id", nodes.c.session_id)
    sa.Index("ix_nodes_session_type", nodes.c.session_id, nodes.c.node_type)
    metadata.create_all(engine)


###############################################################################
def _version(database_path: Path) -> str | None:
    engine = _engine(database_path)
    try:
        with engine.connect() as connection:
            if not inspect(connection).has_table("alembic_version"):
                return None
            return connection.execute(text("select version_num from alembic_version")).scalar_one_or_none()
    finally:
        engine.dispose()


###############################################################################
def test_empty_database_is_created_and_migrated_to_head(tmp_path: Path) -> None:
    database_path = tmp_path / "database.db"

    initialize_sqlite_database(_settings(), db_path=database_path)
    initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert set(inspect(engine).get_table_names()) == {
            "access_keys",
            "alembic_version",
            "chat_history_messages",
            "configuration_profiles",
            "execution_events",
            "execution_runs",
            "execution_steps",
            "user_sessions",
        }
        assert _version(database_path) == "0002_remove_node_configuration_mirror"
    finally:
        engine.dispose()


###############################################################################
def test_migration_engine_enables_foreign_keys(tmp_path: Path) -> None:
    engine = migration._migration_engine(tmp_path / "foreign-keys.db")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


###############################################################################
def test_legacy_schema_is_adopted_without_losing_data(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    engine = _engine(database_path)
    # Test fixture only: emulate the schema created by the pre-Alembic release.
    Base.metadata.create_all(engine)
    _add_legacy_node_table(engine)
    with sa.orm.Session(engine) as session:
        session.add(
            UserSession(
                session_name="legacy-session",
                ollama_base_url="http://localhost:11434",
                ollama_chat_model="llama3.2",
                ollama_embedding_model="nomic-embed-text",
            )
        )
        session.commit()
    engine.dispose()

    initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert _version(database_path) == "0002_remove_node_configuration_mirror"
        assert "nodes" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(
                text("select session_name from user_sessions")
            ).scalar_one() == "legacy-session"
    finally:
        engine.dispose()


###############################################################################
def test_partial_unversioned_schema_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "partial.db"
    engine = _engine(database_path)
    Base.metadata.tables["user_sessions"].create(engine)
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="incomplete"):
        initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert "alembic_version" not in inspect(engine).get_table_names()
        assert "user_sessions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


###############################################################################
def test_unknown_revision_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "unknown-revision.db"
    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(
            text("update alembic_version set version_num = 'unknown_revision'")
        )
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="ancestor"):
        initialize_sqlite_database(_settings(), db_path=database_path)


###############################################################################
def test_versioned_partial_schema_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "versioned-partial.db"
    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(text("drop table execution_events"))
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="incomplete"):
        initialize_sqlite_database(_settings(), db_path=database_path)


###############################################################################
def test_multiple_database_heads_fail_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "multiple-heads.db"
    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(
            text("insert into alembic_version (version_num) values ('other_head')")
        )
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="multiple"):
        initialize_sqlite_database(_settings(), db_path=database_path)


###############################################################################
def _configure_revision_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source_root = common_path.SERVER_ROOT / "migrations"
    migration_root = tmp_path / "migrations"
    shutil.copytree(source_root, migration_root)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.alembic]\n"
        'script_location = "%(here)s/migrations"\n'
        'prepend_sys_path = ["%(here)s/.."]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(common_path, "SERVER_ROOT", tmp_path)
    return migration_root


###############################################################################
def _add_marker_revision(migration_root: Path, *, failing: bool = False) -> None:
    (migration_root / "versions" / "0002_marker.py").write_text(
        '''"""Add a marker column for migration integration tests."""\n\n'''
        "from alembic import op\n"
        "import sqlalchemy as sa\n\n"
        "revision = '0003_marker'\n"
        "down_revision = '0002_remove_node_configuration_mirror'\n"
        "branch_labels = None\n"
        "depends_on = None\n\n"
        "def upgrade():\n"
        "    op.add_column('user_sessions', sa.Column('migration_marker', sa.String(), nullable=True))\n\n"
        "def downgrade():\n"
        "    with op.batch_alter_table('user_sessions') as batch_op:\n"
        "        batch_op.drop_column('migration_marker')\n",
        encoding="utf-8",
    )
    if failing:
        (migration_root / "versions" / "0003_failure.py").write_text(
            '''"""Fail after issuing DDL to verify rollback."""\n\n'''
            "from alembic import op\n"
            "import sqlalchemy as sa\n\n"
            "revision = '0004_failure'\n"
            "down_revision = '0003_marker'\n"
            "branch_labels = None\n"
            "depends_on = None\n\n"
            "def upgrade():\n"
            "    op.add_column('user_sessions', sa.Column('failure_marker', sa.String(), nullable=True))\n"
            "    raise RuntimeError('intentional migration failure')\n\n"
            "def downgrade():\n"
            "    pass\n",
            encoding="utf-8",
        )


###############################################################################
def _apply_revision(
    database_path: Path, revision: str, *, downgrade: bool = False
) -> None:
    config = migration._alembic_config(database_path)
    engine = migration._migration_engine(database_path)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            if downgrade:
                command.downgrade(config, revision)
            else:
                command.upgrade(config, revision)
    finally:
        engine.dispose()


###############################################################################
def test_outdated_database_is_upgraded_to_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    migration_root = _configure_revision_tree(tmp_path / "project", monkeypatch)
    _add_marker_revision(migration_root)
    database_path = tmp_path / "outdated.db"

    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with sa.orm.Session(engine) as session:
        session.add(
            UserSession(
                session_name="behind-session",
                ollama_base_url="http://localhost:11434",
                ollama_chat_model="llama3.2",
                ollama_embedding_model="nomic-embed-text",
            )
        )
        session.commit()
    engine.dispose()

    _apply_revision(database_path, migration.BASELINE_REVISION, downgrade=True)
    initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert _version(database_path) == "0003_marker"
        assert "migration_marker" in {
            column["name"] for column in inspect(engine).get_columns("user_sessions")
        }
        with engine.connect() as connection:
            assert connection.execute(
                text("select session_name from user_sessions")
            ).scalar_one() == "behind-session"
    finally:
        engine.dispose()


###############################################################################
def test_failed_migration_rolls_back_ddl_and_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    migration_root = _configure_revision_tree(tmp_path / "project", monkeypatch)
    _add_marker_revision(migration_root, failing=True)
    database_path = tmp_path / "rollback.db"

    _apply_revision(database_path, "0003_marker")

    with pytest.raises(migration.DatabaseMigrationError, match="failed"):
        migration.run_database_migrations(database_path)

    engine = _engine(database_path)
    try:
        columns = {column["name"] for column in inspect(engine).get_columns("user_sessions")}
        assert "failure_marker" not in columns
        assert _version(database_path) == "0003_marker"
    finally:
        engine.dispose()


###############################################################################
def test_concurrent_initialization_is_serialized(tmp_path: Path) -> None:
    database_path = tmp_path / "concurrent.db"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                initialize_sqlite_database,
                _settings(),
                db_path=database_path,
            )
            for _ in range(2)
        ]
        for future in futures:
            future.result()

    assert _version(database_path) == "0002_remove_node_configuration_mirror"


###############################################################################
def test_migration_lock_timeout_is_reported_as_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "locked.db"
    lock_path = database_path.with_name("locked.db.migration.lock")
    held_lock = portalocker.Lock(str(lock_path), mode="a", timeout=0)
    held_lock.acquire()
    monkeypatch.setattr(migration, "MIGRATION_LOCK_TIMEOUT_SECONDS", 0.01)
    try:
        with pytest.raises(migration.DatabaseMigrationError, match="Timed out"):
            migration.run_database_migrations(database_path)
    finally:
        held_lock.release()
