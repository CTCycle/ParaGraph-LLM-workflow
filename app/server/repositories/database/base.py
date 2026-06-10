from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd
import sqlalchemy
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    delete,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session, sessionmaker

from server.common.utils.logger import logger
from server.repositories.database.utils import normalize_string_columns
from server.repositories.schemas import Base

###############################################################################
class TabularDatabaseRepository:

    # -------------------------------------------------------------------------
    def __init__(
        self,
        *,
        engine: Engine,
        db_path: str | None,
        insert_batch_size: int,
    ) -> None:
        self.db_path = db_path
        self.engine = engine
        self.session = sessionmaker(bind=self.engine, future=True)
        self.insert_batch_size = insert_batch_size

    # -------------------------------------------------------------------------
    def _model_for_table(self, table_name: str) -> type[Any] | None:
        for mapper in Base.registry.mappers:
            model = mapper.class_
            if getattr(model, "__tablename__", None) == table_name:
                return model
        return None

    # -------------------------------------------------------------------------
    def _reflect_table(self, table_name: str) -> Table | None:
        metadata = MetaData()
        try:
            return Table(table_name, metadata, autoload_with=self.engine)
        except NoSuchTableError:
            return None

    # -------------------------------------------------------------------------
    def _column_type_for_series(self, series: pd.Series) -> sqlalchemy.types.TypeEngine:
        if pd.api.types.is_bool_dtype(series):
            return Boolean()
        if pd.api.types.is_integer_dtype(series):
            return Integer()
        if pd.api.types.is_float_dtype(series):
            return Float()
        if pd.api.types.is_datetime64_any_dtype(series):
            return DateTime(timezone=False)
        return Text()

    # -------------------------------------------------------------------------
    def _create_table_from_dataframe(self, table_name: str, df: pd.DataFrame) -> Table:
        if len(df.columns) == 0:
            raise ValueError(
                f"Cannot create table '{table_name}' from a dataframe with no columns"
            )

        metadata = MetaData()
        columns: list[Column[Any]] = []
        for column_name in df.columns:
            normalized_name = str(column_name).strip()
            if not normalized_name:
                raise ValueError(
                    f"Table '{table_name}' contains an invalid empty column name"
                )
            columns.append(
                Column(
                    normalized_name,
                    self._column_type_for_series(df[column_name]),
                    nullable=True,
                )
            )

        table = Table(table_name, metadata, *columns)
        metadata.create_all(self.engine, tables=[table])
        return table

    # -------------------------------------------------------------------------
    def _records_from_dataframe(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        normalized_df = normalize_string_columns(df)
        return normalized_df.to_dict(orient="records")

    # -------------------------------------------------------------------------
    def _iter_batches(
        self, records: list[dict[str, Any]]
    ) -> Iterator[list[dict[str, Any]]]:
        if not records:
            return
        batch_size = max(1, self.insert_batch_size)
        for start in range(0, len(records), batch_size):
            yield records[start : start + batch_size]

    # -------------------------------------------------------------------------
    def load_from_database(
        self,
        table_name: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        model = self._model_for_table(table_name)
        with Session(self.engine) as db_session:
            if model is not None:
                statement = select(model)
                if offset:
                    statement = statement.offset(offset)
                if limit is not None:
                    statement = statement.limit(limit)
                rows = db_session.scalars(statement).all()
                columns = [column.name for column in model.__table__.columns]
                payload = [
                    {column: getattr(row, column) for column in columns} for row in rows
                ]
                return pd.DataFrame(payload, columns=columns).reset_index(drop=True)

            table = self._reflect_table(table_name)
            if table is None:
                logger.warning("Table %s does not exist", table_name)
                return pd.DataFrame()

            statement = select(table)
            if offset:
                statement = statement.offset(offset)
            if limit is not None:
                statement = statement.limit(limit)
            rows = db_session.execute(statement).mappings().all()
            columns = [column.name for column in table.columns]
            payload = [dict(row) for row in rows]
            return pd.DataFrame(payload, columns=columns).reset_index(drop=True)

    # -------------------------------------------------------------------------
    def save_into_database(self, df: pd.DataFrame, table_name: str) -> None:
        records = self._records_from_dataframe(df)
        with Session(self.engine) as db_session:
            model = self._model_for_table(table_name)
            if model is not None:
                db_session.execute(delete(model))
                for batch in self._iter_batches(records):
                    db_session.bulk_insert_mappings(model, batch)
                db_session.commit()
                return

            table = self._reflect_table(table_name)
            if table is None:
                table = self._create_table_from_dataframe(table_name, df)

            db_session.execute(delete(table))
            for batch in self._iter_batches(records):
                db_session.execute(insert(table), batch)
            db_session.commit()

    # -------------------------------------------------------------------------
    def count_rows(self, table_name: str) -> int:
        model = self._model_for_table(table_name)
        with Session(self.engine) as db_session:
            if model is not None:
                value = db_session.scalar(select(func.count()).select_from(model)) or 0
                return int(value)

            table = self._reflect_table(table_name)
            if table is None:
                raise ValueError(f"Table {table_name} does not exist")
            value = db_session.scalar(select(func.count()).select_from(table)) or 0
            return int(value)
