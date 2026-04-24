from __future__ import annotations

import pandas as pd

# -----------------------------------------------------------------------------
def normalize_postgres_engine(engine: str | None) -> str:
    if not engine:
        return "postgresql+psycopg"
    lowered = engine.lower()
    if lowered in {"postgres", "postgresql"}:
        return "postgresql+psycopg"
    return engine


# -----------------------------------------------------------------------------
def normalize_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in normalized.columns:
        if pd.api.types.is_string_dtype(
            normalized[column]
        ) or pd.api.types.is_object_dtype(normalized[column]):
            object_series = normalized[column].astype(object)
            normalized[column] = object_series.where(object_series.notna(), None)
    return normalized


