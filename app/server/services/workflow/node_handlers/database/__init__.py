from __future__ import annotations

from server.domain.node_handler_database import (
    CrudCreateParameters,
    CrudDeleteParameters,
    CrudReadParameters,
    CrudUpdateParameters,
    CustomSqlQueryParameters,
)
from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.database.operations import (
    _crud_create_executor,
    _crud_delete_executor,
    _crud_read_executor,
    _crud_update_executor,
    _custom_sql_query_executor,
)


DATABASE_HANDLERS = {
    "crud_create": NodeHandler(
        executor=_crud_create_executor, parameter_model=CrudCreateParameters
    ),
    "crud_read": NodeHandler(
        executor=_crud_read_executor, parameter_model=CrudReadParameters
    ),
    "crud_update": NodeHandler(
        executor=_crud_update_executor, parameter_model=CrudUpdateParameters
    ),
    "crud_delete": NodeHandler(
        executor=_crud_delete_executor, parameter_model=CrudDeleteParameters
    ),
    "custom_sql_query": NodeHandler(
        executor=_custom_sql_query_executor, parameter_model=CustomSqlQueryParameters
    ),
}

__all__ = ["DATABASE_HANDLERS"]
