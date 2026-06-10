from __future__ import annotations

from typing import Any

from server.domain.node_handler_database import (
    CrudCreateParameters,
    CrudDeleteParameters,
    CrudReadParameters,
    CrudUpdateParameters,
    CustomSqlQueryParameters,
)
from server.repositories.workflow.database import (
    execute_create,
    execute_custom_sql,
    execute_delete,
    execute_read,
    execute_update,
)


###############################################################################
def _connection(inputs: dict[str, Any]) -> dict[str, Any]:
    value = inputs.get("connection")
    if not isinstance(value, dict):
        raise ValueError("Database operation nodes require a connection controller")
    return value


###############################################################################
def _merged_json_input(
    parameters: dict[str, Any], inputs: dict[str, Any], name: str
) -> dict[str, Any]:
    raw_value = inputs.get(name) if name in inputs else parameters.get(name)
    if raw_value in (None, ""):
        return {}
    if not isinstance(raw_value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return raw_value


###############################################################################
def _crud_create_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = CrudCreateParameters.model_validate(
        {**parameters, "values": _merged_json_input(parameters, inputs, "values")}
    )
    return {
        "dataset": execute_create(
            _connection(inputs), table_name=parsed.table, values=parsed.values
        )
    }


###############################################################################
def _crud_read_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = CrudReadParameters.model_validate(
        {**parameters, "filters": _merged_json_input(parameters, inputs, "filters")}
    )
    return {
        "dataset": execute_read(
            _connection(inputs),
            table_name=parsed.table,
            columns=parsed.columns,
            filters=parsed.filters,
            limit=parsed.limit,
            order_by=parsed.order_by,
        )
    }


###############################################################################
def _crud_update_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = CrudUpdateParameters.model_validate(
        {
            **parameters,
            "values": _merged_json_input(parameters, inputs, "values"),
            "filters": _merged_json_input(parameters, inputs, "filters"),
        }
    )
    return {
        "dataset": execute_update(
            _connection(inputs),
            table_name=parsed.table,
            values=parsed.values,
            filters=parsed.filters,
        )
    }


###############################################################################
def _crud_delete_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = CrudDeleteParameters.model_validate(
        {**parameters, "filters": _merged_json_input(parameters, inputs, "filters")}
    )
    return {
        "dataset": execute_delete(
            _connection(inputs), table_name=parsed.table, filters=parsed.filters
        )
    }


###############################################################################
def _custom_sql_query_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = CustomSqlQueryParameters.model_validate(parameters)
    return {"dataset": execute_custom_sql(_connection(inputs), sql=parsed.sql)}


__all__ = [
    "_crud_create_executor",
    "_crud_delete_executor",
    "_crud_read_executor",
    "_crud_update_executor",
    "_custom_sql_query_executor",
]
