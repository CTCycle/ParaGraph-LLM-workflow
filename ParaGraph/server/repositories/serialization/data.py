from __future__ import annotations

import pandas as pd

from ParaGraph.server.common.constants import DATASETS_TABLE
from ParaGraph.server.repositories.database import database


###############################################################################
class DataSerializer:
    """Template persistence adapter for dataset/workflow data."""

    def load_dataset_index(self) -> pd.DataFrame:
        return database.load_from_database(DATASETS_TABLE)

    def has_data(self) -> bool:
        return database.count_rows(DATASETS_TABLE) > 0

    def save_dataset_index(self, df: pd.DataFrame) -> None:
        database.upsert_into_database(df, DATASETS_TABLE)

    def load_training_data(
        self,
        only_metadata: bool = False,
        dataset_name: str | None = None,
    ) -> (
        tuple[pd.DataFrame, pd.DataFrame, dict[str, object]] | dict[str, object] | None
    ):
        # Placeholder payload for template.
        if only_metadata:
            return {"dataset_name": dataset_name or "default", "source": "template"}
        train = pd.DataFrame({"id": [1], "feature": ["placeholder"]})
        validation = pd.DataFrame({"id": [1], "feature": ["placeholder"]})
        metadata = {"dataset_name": dataset_name or "default"}
        return train, validation, metadata
