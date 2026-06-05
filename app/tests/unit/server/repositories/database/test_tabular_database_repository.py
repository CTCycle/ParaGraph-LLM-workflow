from __future__ import annotations

import pandas as pd
import pytest
import sqlalchemy

from server.repositories.database.base import TabularDatabaseRepository


###############################################################################
class InMemoryTabularRepository(TabularDatabaseRepository):
    def __init__(self, insert_batch_size: int = 2) -> None:
        engine = sqlalchemy.create_engine("sqlite:///:memory:", future=True)
        super().__init__(
            engine=engine,
            db_path=None,
            insert_batch_size=insert_batch_size,
        )


###############################################################################
def test_save_load_and_count_dynamic_table() -> None:
    repository = InMemoryTabularRepository()
    frame = pd.DataFrame(
        [
            {
                "name": "dataset-a",
                "row_count": 10,
                "score": 0.75,
                "enabled": True,
            },
            {
                "name": "dataset-b",
                "row_count": 12,
                "score": 0.9,
                "enabled": False,
            },
        ]
    )

    repository.save_into_database(frame, "dynamic_datasets")

    loaded = repository.load_from_database("dynamic_datasets")
    assert repository.count_rows("dynamic_datasets") == 2
    assert list(loaded.columns) == ["name", "row_count", "score", "enabled"]
    assert len(loaded) == 2


###############################################################################
def test_save_replaces_existing_dynamic_table_rows() -> None:
    repository = InMemoryTabularRepository()
    repository.save_into_database(
        pd.DataFrame(
            [
                {"name": "old-a", "value": 1},
                {"name": "old-b", "value": 2},
            ]
        ),
        "replaceable_datasets",
    )

    repository.save_into_database(
        pd.DataFrame([{"name": "new-a", "value": 3}]),
        "replaceable_datasets",
    )

    loaded = repository.load_from_database("replaceable_datasets")
    assert repository.count_rows("replaceable_datasets") == 1
    assert loaded.to_dict(orient="records") == [{"name": "new-a", "value": 3}]


###############################################################################
def test_load_missing_table_returns_empty_dataframe() -> None:
    repository = InMemoryTabularRepository()

    loaded = repository.load_from_database("missing_table")

    assert loaded.empty


###############################################################################
def test_count_missing_table_raises_value_error() -> None:
    repository = InMemoryTabularRepository()

    with pytest.raises(ValueError, match="does not exist"):
        repository.count_rows("missing_table")
