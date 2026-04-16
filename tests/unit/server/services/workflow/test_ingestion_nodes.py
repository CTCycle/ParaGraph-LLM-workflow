from __future__ import annotations

from pathlib import Path

from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ParaGraph.server.services.workflow import node_registry


def test_load_documents_emits_deferred_records_without_eager_text(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "one.txt").write_text("alpha", encoding="utf-8")
    (source_dir / "two.md").write_text("beta", encoding="utf-8")
    (source_dir / "skip.bin").write_bytes(b"\x00\x01")

    payload = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": False},
        {},
    )

    assert [Path(document["source_uri"]).name for document in payload["documents"]] == [
        "one.txt",
        "two.md",
    ]
    assert all(document["text"] == "" for document in payload["documents"])
    assert all(
        document["metadata"]["deferred_load"] is True
        for document in payload["documents"]
    )


def test_load_documents_respects_recursive_toggle(tmp_path: Path) -> None:
    source_dir = tmp_path / "collection"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "root.txt").write_text("root", encoding="utf-8")
    (nested_dir / "child.txt").write_text("child", encoding="utf-8")

    non_recursive = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": False},
        {},
    )
    recursive = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": True},
        {},
    )

    assert [
        Path(document["source_uri"]).name for document in non_recursive["documents"]
    ] == ["root.txt"]
    assert sorted(
        Path(document["source_uri"]).name for document in recursive["documents"]
    ) == ["child.txt", "root.txt"]


def test_load_documents_rejects_non_canonical_folder_path_keys(tmp_path: Path) -> None:
    source_dir = tmp_path / "legacy-folder"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "legacy.txt").write_text("legacy", encoding="utf-8")

    invalid_payloads = [
        {"folderPath": str(source_dir), "recursive": False},
        {"folder path": str(source_dir), "recursive": False},
        {"directory_path": str(source_dir), "recursive": False},
        {"path": str(source_dir), "recursive": False},
    ]

    for payload in invalid_payloads:
        try:
            node_registry.execute("LOAD_DOCUMENTS", 1, payload, {})
        except ValueError as exc:
            assert "folder_path" in str(exc)
        else:
            raise AssertionError(
                "Expected LOAD_DOCUMENTS to reject non-canonical folder path keys"
            )


def test_sql_file_database_node_roundtrip(tmp_path: Path) -> None:
    class ItemsBase(DeclarativeBase):
        pass

    class Item(ItemsBase):
        __tablename__ = "items"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        name: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / "file_dataset.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    ItemsBase.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(Item(name="alpha"))
        db_session.commit()
    engine.dispose()

    connection_payload = node_registry.execute(
        "SQL_FILE_DATABASE",
        1,
        {
            "db_path": str(database_path),
            "db_connect_timeout": 30,
        },
        {},
    )

    assert connection_payload["connection"]["engine"] == "sqlite"
    assert connection_payload["connection"]["file_path"] == str(database_path.resolve())
    assert connection_payload["connection"]["read_only"] is True
    assert connection_payload["connection"]["database_name"] == "file_dataset"


def test_sql_database_requires_required_fields_before_connect_attempt() -> None:
    try:
        node_registry.execute(
            "SQL_DATABASE",
            1,
            {
                "db_engine": "postgres",
                "db_host": "",
                "db_port": 5432,
                "db_name": "",
                "db_user": "postgres",
                "db_password": "change_me",
                "db_ssl": False,
                "db_ssl_ca": "",
                "db_connect_timeout": 30,
            },
            {},
        )
    except ValueError as exc:
        message = str(exc)
        assert "db_host" in message or "db_name" in message
    else:
        raise AssertionError(
            "Expected SQL_DATABASE validation failure for missing required fields"
        )
