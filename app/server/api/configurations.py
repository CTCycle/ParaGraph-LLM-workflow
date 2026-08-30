from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from server.contracts.configuration import (
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    DEFAULT_SESSION_NAME,
    OllamaPingRequest,
    OllamaStatusResponse,
    PROFILE_NAME_PATTERN,
    ProviderPingRequest,
    ProviderStatusResponse,
    SESSION_NAME_PATTERN,
)
from server.services.configuration import configuration_service


router = APIRouter(prefix="/configurations", tags=["configurations"])


###############################################################################
@router.get("", response_model=AppConfigurationPayload)
def load_configurations(
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> AppConfigurationPayload:
    return configuration_service.load_public_configuration(session_name=session_name)


###############################################################################
@router.put("", response_model=AppConfigurationPayload)
def save_configurations(payload: AppConfigurationPayload) -> AppConfigurationPayload:
    return configuration_service.save_public_configuration(payload)


###############################################################################
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


###############################################################################
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
        return configuration_service.load_public_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )
    except KeyError as exc:
        detail = exc.args[0] if exc.args else str(exc)
        raise HTTPException(status_code=404, detail=detail) from exc


###############################################################################
@router.put("/profiles/{profile_name}", response_model=AppConfigurationPayload)
def save_configuration_profile(
    payload: AppConfigurationPayload,
    profile_name: str = Path(
        ..., min_length=1, max_length=120, pattern=PROFILE_NAME_PATTERN
    ),
) -> AppConfigurationPayload:
    try:
        return configuration_service.save_public_configuration_profile(
            profile_name=profile_name, payload=payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


###############################################################################
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


###############################################################################
@router.post("/providers/ping", response_model=ProviderStatusResponse)
def ping_provider(
    payload: ProviderPingRequest,
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> ProviderStatusResponse:
    return configuration_service.ping_provider(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        session_name=session_name,
    )
