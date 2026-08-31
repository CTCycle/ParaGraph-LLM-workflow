from __future__ import annotations

from typing import Any

from server.contracts.configuration import (
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    OllamaStatusResponse,
    ProviderConfiguration,
    ProviderStatusResponse,
)
from server.repositories.configuration import (
    ConfigurationRepository,
    configuration_repository,
)
from server.services.llm.providers import (
    LLMError,
    OllamaClient,
    OllamaError,
    OpenAICompatibleLocalClient,
)
from server.services.workflow.provider.registry import provider_registry_entry


###############################################################################
class ConfigurationService:
    # -------------------------------------------------------------------------
    def __init__(self, repository: ConfigurationRepository | None = None) -> None:
        self._repository = repository or configuration_repository

    # -------------------------------------------------------------------------
    def load_configuration(
        self, session_name: str | None = None
    ) -> AppConfigurationPayload:
        payload = self._repository.load_configuration(session_name=session_name)
        return AppConfigurationPayload.model_validate(payload)

    # -------------------------------------------------------------------------
    def load_public_configuration(
        self, session_name: str | None = None
    ) -> AppConfigurationPayload:
        return self._mask_configuration_secrets(
            self.load_configuration(session_name=session_name)
        )

    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_provider_secrets(
        payload: AppConfigurationPayload,
        existing: AppConfigurationPayload | None,
    ) -> list[dict[str, Any]]:
        existing_by_provider = {
            item.provider: item for item in (existing.provider_configurations if existing else [])
        }
        resolved: list[dict[str, Any]] = []
        for item in payload.provider_configurations:
            raw = item.model_dump(mode="json", exclude={"has_api_key"})
            if item.api_key is None and item.has_api_key:
                current = existing_by_provider.get(item.provider)
                raw["api_key"] = current.api_key if current else None
            resolved.append(raw)
        return resolved

    # -------------------------------------------------------------------------
    def save_configuration(
        self, payload: AppConfigurationPayload
    ) -> AppConfigurationPayload:
        existing = AppConfigurationPayload.model_validate(
            self._repository.load_configuration(session_name=payload.session_name)
        )
        stored = self._repository.save_configuration(
            session_name=payload.session_name,
            provider_configurations=self._resolve_provider_secrets(payload, existing),
        )
        return AppConfigurationPayload.model_validate(stored)

    # -------------------------------------------------------------------------
    def save_public_configuration(
        self, payload: AppConfigurationPayload
    ) -> AppConfigurationPayload:
        return self._mask_configuration_secrets(self.save_configuration(payload))

    # -------------------------------------------------------------------------
    def list_configuration_profiles(
        self, session_name: str | None = None
    ) -> ConfigurationProfileListResponse:
        payload = self._repository.list_configuration_profiles(
            session_name=session_name
        )
        return ConfigurationProfileListResponse.model_validate(payload)

    # -------------------------------------------------------------------------
    def load_configuration_profile(
        self, *, session_name: str | None, profile_name: str
    ) -> AppConfigurationPayload:
        payload = self._repository.load_configuration_profile(
            session_name=session_name,
            profile_name=profile_name,
        )
        return AppConfigurationPayload.model_validate(payload)

    # -------------------------------------------------------------------------
    def resolve_provider_configuration(
        self, *, profile_name: str, provider: str
    ) -> ProviderConfiguration:
        """Resolve one saved provider credential without changing active config."""
        normalized_profile_name = profile_name.strip()
        normalized_provider = provider.strip().lower()
        if not normalized_profile_name:
            raise ValueError("credential_profile is required")
        if not normalized_provider:
            raise ValueError("credential provider is required")

        profile = self.load_configuration_profile(
            session_name=None, profile_name=normalized_profile_name
        )
        provider_names = {normalized_provider}
        if normalized_provider in {"postgres", "postgresql"}:
            provider_names.update({"postgres", "postgresql"})
        provider_configuration = next(
            (
                item
                for item in profile.provider_configurations
                if item.provider in provider_names
            ),
            None,
        )
        if provider_configuration is None or not provider_configuration.api_key:
            raise ValueError(
                f"Credential profile '{normalized_profile_name}' has no credential for provider '{normalized_provider}'"
            )
        return provider_configuration

    # -------------------------------------------------------------------------
    def load_public_configuration_profile(
        self, *, session_name: str | None, profile_name: str
    ) -> AppConfigurationPayload:
        return self._mask_configuration_secrets(
            self.load_configuration_profile(
                session_name=session_name, profile_name=profile_name
            )
        )

    # -------------------------------------------------------------------------
    def save_configuration_profile(
        self,
        *,
        profile_name: str,
        payload: AppConfigurationPayload,
    ) -> AppConfigurationPayload:
        existing: AppConfigurationPayload | None = None
        try:
            existing = self.load_configuration_profile(
                session_name=payload.session_name, profile_name=profile_name
            )
        except KeyError:
            pass

        configuration_json = {
            "session_name": payload.session_name,
            "provider_configurations": self._resolve_provider_secrets(payload, existing),
        }
        self._repository.save_configuration_profile(
            session_name=payload.session_name,
            profile_name=profile_name,
            configuration_json=configuration_json,
        )
        return AppConfigurationPayload.model_validate(configuration_json)

    # -------------------------------------------------------------------------
    def save_public_configuration_profile(
        self,
        *,
        profile_name: str,
        payload: AppConfigurationPayload,
    ) -> AppConfigurationPayload:
        return self._mask_configuration_secrets(
            self.save_configuration_profile(profile_name=profile_name, payload=payload)
        )

    # -------------------------------------------------------------------------
    def _active_provider_configuration(
        self, *, provider: str, session_name: str | None
    ) -> ProviderConfiguration | None:
        normalized_provider = provider.strip().lower()
        return next(
            (
                item
                for item in self.load_configuration(
                    session_name=session_name
                ).provider_configurations
                if item.provider == normalized_provider
            ),
            None,
        )

    # -------------------------------------------------------------------------
    def ping_ollama(
        self, *, base_url: str | None, session_name: str | None = None
    ) -> OllamaStatusResponse:
        provider_configuration = self._active_provider_configuration(
            provider="ollama", session_name=session_name
        )
        resolved_base_url = (
            base_url
            or (provider_configuration.base_url if provider_configuration else None)
            or provider_registry_entry("ollama").default_base_url
        )
        assert resolved_base_url is not None

        try:
            models = OllamaClient(base_url=resolved_base_url).list_models()
            count = len(models)
            suffix = "" if count == 1 else "s"
            return OllamaStatusResponse(
                ok=True,
                message=f"Ollama reachable ({count} model{suffix} discovered).",
                base_url=resolved_base_url,
                model_count=count,
            )
        except (ValueError, OllamaError) as exc:
            return OllamaStatusResponse(
                ok=False,
                message=f"Ollama unreachable: {exc}",
                base_url=resolved_base_url,
                model_count=0,
            )

    # -------------------------------------------------------------------------
    def ping_provider(
        self,
        *,
        provider: str,
        base_url: str | None,
        api_key: str | None,
        session_name: str | None = None,
    ) -> ProviderStatusResponse:
        normalized_provider = provider.strip().lower()
        provider_configuration = self._active_provider_configuration(
            provider=normalized_provider, session_name=session_name
        )
        resolved_base_url = base_url or (
            provider_configuration.base_url if provider_configuration else None
        )
        resolved_api_key = api_key or (
            provider_configuration.api_key if provider_configuration else None
        )

        try:
            if normalized_provider == "ollama":
                status = self.ping_ollama(
                    base_url=resolved_base_url, session_name=session_name
                )
                return ProviderStatusResponse(
                    ok=status.ok,
                    provider=normalized_provider,
                    message=status.message,
                    base_url=status.base_url,
                    model_count=status.model_count,
                )

            metadata = provider_registry_entry(normalized_provider)
            if not metadata.supports_status_check:
                return ProviderStatusResponse(
                    ok=False,
                    provider=normalized_provider,
                    message=f"Provider '{normalized_provider}' does not support status checks.",
                    base_url=resolved_base_url or "",
                    model_count=0,
                )

            client = OpenAICompatibleLocalClient(
                provider=normalized_provider,
                base_url=resolved_base_url,
                api_key=resolved_api_key,
            )
            models = client.list_models()
            count = len(models)
            suffix = "" if count == 1 else "s"
            return ProviderStatusResponse(
                ok=True,
                provider=normalized_provider,
                message=f"{normalized_provider} reachable ({count} model{suffix} discovered).",
                base_url=client.base_url,
                model_count=count,
            )
        except (ValueError, LLMError, OllamaError) as exc:
            return ProviderStatusResponse(
                ok=False,
                provider=normalized_provider,
                message=f"{normalized_provider} unreachable: {exc}",
                base_url=resolved_base_url or "",
                model_count=0,
            )

    # -------------------------------------------------------------------------
    @staticmethod
    def _mask_configuration_secrets(
        payload: AppConfigurationPayload,
    ) -> AppConfigurationPayload:
        return payload.model_copy(
            update={
                "provider_configurations": [
                    item.model_copy(
                        update={
                            "api_key": None,
                            "has_api_key": bool(item.api_key) or item.has_api_key,
                        }
                    )
                    for item in payload.provider_configurations
                ]
            }
        )


configuration_service = ConfigurationService()
