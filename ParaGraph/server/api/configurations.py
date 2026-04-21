from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from ParaGraph.server.domain.configuration import (
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    DEFAULT_SESSION_NAME,
    MASKED_API_KEY_VALUE,
    OllamaPingRequest,
    OllamaStatusResponse,
)
from ParaGraph.server.services.configuration import configuration_service


router = APIRouter(prefix="/configurations", tags=["configurations"])
SESSION_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$"
PROFILE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}$"


def _sanitize_payload(payload: AppConfigurationPayload) -> AppConfigurationPayload:
    sanitized = payload.model_copy(deep=True)
    sanitized.access_keys = [
        item.model_copy(
            update={
                "api_key": MASKED_API_KEY_VALUE if item.api_key else None
            }
        )
        for item in sanitized.access_keys
    ]
    return sanitized


@router.get("", response_model=AppConfigurationPayload)
def load_configurations(
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> AppConfigurationPayload:
    payload = configuration_service.load_configuration(session_name=session_name)
    return _sanitize_payload(payload)


@router.put("", response_model=AppConfigurationPayload)
def save_configurations(payload: AppConfigurationPayload) -> AppConfigurationPayload:
    stored = configuration_service.save_configuration(payload)
    return _sanitize_payload(stored)


@router.get("/profiles", response_model=ConfigurationProfileListResponse)
def list_configuration_profiles(
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> ConfigurationProfileListResponse:
    return configuration_service.list_configuration_profiles(session_name=session_name)


@router.get("/profiles/{profile_name}", response_model=AppConfigurationPayload)
def load_configuration_profile(
    profile_name: str = Path(
        ..., min_length=1, max_length=120, pattern=PROFILE_NAME_PATTERN
    ),
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> AppConfigurationPayload:
    try:
        payload = configuration_service.load_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )
        return _sanitize_payload(payload)
    except KeyError as exc:
        detail = exc.args[0] if exc.args else str(exc)
        raise HTTPException(status_code=404, detail=detail) from exc


@router.put("/profiles/{profile_name}", response_model=AppConfigurationPayload)
def save_configuration_profile(
    payload: AppConfigurationPayload,
    profile_name: str = Path(
        ..., min_length=1, max_length=120, pattern=PROFILE_NAME_PATTERN
    ),
) -> AppConfigurationPayload:
    try:
        stored = configuration_service.save_configuration_profile(
            profile_name=profile_name, payload=payload
        )
        return _sanitize_payload(stored)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ollama/ping", response_model=OllamaStatusResponse)
def ping_ollama(
    payload: OllamaPingRequest,
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> OllamaStatusResponse:
    return configuration_service.ping_ollama(
        base_url=payload.base_url, session_name=session_name
    )
