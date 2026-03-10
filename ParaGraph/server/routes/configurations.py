from __future__ import annotations

from fastapi import APIRouter, Query

from ParaGraph.server.entities.configuration import AppConfigurationPayload, DEFAULT_SESSION_NAME
from ParaGraph.server.services.configuration import configuration_service


router = APIRouter(prefix="/configurations", tags=["configurations"])


@router.get("", response_model=AppConfigurationPayload)
def load_configurations(
    session_name: str = Query(default=DEFAULT_SESSION_NAME, min_length=1, max_length=120),
) -> AppConfigurationPayload:
    return configuration_service.load_configuration(session_name=session_name)


@router.put("", response_model=AppConfigurationPayload)
def save_configurations(payload: AppConfigurationPayload) -> AppConfigurationPayload:
    return configuration_service.save_configuration(payload)
