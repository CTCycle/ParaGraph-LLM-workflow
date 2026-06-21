from __future__ import annotations

from server.domain.configuration import (
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    MASKED_API_KEY_VALUE,
    OllamaStatusResponse,
    ProviderStatusResponse,
    is_masked_api_key,
)
from server.domain.node_catalog import NodeManifest
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
        payload = self.load_configuration(session_name=session_name)
        return self._mask_configuration_secrets(payload)

    # -------------------------------------------------------------------------
    def save_configuration(
        self, payload: AppConfigurationPayload
    ) -> AppConfigurationPayload:
        existing_payload = self._repository.load_configuration(
            session_name=payload.session_name
        )
        existing = AppConfigurationPayload.model_validate(existing_payload)
        existing_by_provider = {item.provider: item for item in existing.access_keys}

        resolved_access_keys = []
        for item in payload.access_keys:
            incoming = item.model_dump(mode="json")
            if is_masked_api_key(item.api_key):
                current = existing_by_provider.get(item.provider)
                incoming["api_key"] = current.api_key if current else None
            resolved_access_keys.append(incoming)

        stored = self._repository.save_configuration(
            session_name=payload.session_name,
            access_keys=resolved_access_keys,
            ollama=payload.ollama.model_dump(mode="json"),
        )
        return AppConfigurationPayload.model_validate(stored)

    # -------------------------------------------------------------------------
    def save_public_configuration(
        self, payload: AppConfigurationPayload
    ) -> AppConfigurationPayload:
        stored = self.save_configuration(payload)
        return self._mask_configuration_secrets(stored)

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
        profile_payload = self._repository.load_configuration_profile(
            session_name=session_name,
            profile_name=profile_name,
        )
        stored = self._repository.save_configuration(
            session_name=profile_payload["session_name"],
            access_keys=profile_payload.get("access_keys", []),
            ollama=profile_payload.get("ollama", {}),
        )
        return AppConfigurationPayload.model_validate(stored)

    # -------------------------------------------------------------------------
    def load_public_configuration_profile(
        self, *, session_name: str | None, profile_name: str
    ) -> AppConfigurationPayload:
        payload = self.load_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )
        return self._mask_configuration_secrets(payload)

    # -------------------------------------------------------------------------
    def save_configuration_profile(
        self,
        *,
        profile_name: str,
        payload: AppConfigurationPayload,
    ) -> AppConfigurationPayload:
        stored = self.save_configuration(payload)
        raw_configuration = self._repository.load_configuration(
            session_name=stored.session_name
        )
        self._repository.save_configuration_profile(
            session_name=stored.session_name,
            profile_name=profile_name,
            configuration_json=raw_configuration,
        )
        return stored

    # -------------------------------------------------------------------------
    def save_public_configuration_profile(
        self,
        *,
        profile_name: str,
        payload: AppConfigurationPayload,
    ) -> AppConfigurationPayload:
        stored = self.save_configuration_profile(
            profile_name=profile_name, payload=payload
        )
        return self._mask_configuration_secrets(stored)

    # -------------------------------------------------------------------------
    def ping_ollama(
        self, *, base_url: str | None, session_name: str | None = None
    ) -> OllamaStatusResponse:
        resolved_base_url = base_url
        if not resolved_base_url:
            resolved_base_url = self.load_configuration(
                session_name=session_name
            ).ollama.base_url

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
        access_key = None
        for item in self.load_configuration(session_name=session_name).access_keys:
            if item.provider == normalized_provider:
                access_key = item
                break

        resolved_base_url = base_url or (access_key.base_url if access_key else None)
        resolved_api_key = api_key or (access_key.api_key if access_key else None)

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

            if normalized_provider not in {"lmstudio", "llama"}:
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
    def save_node_manifest(
        self, manifest: NodeManifest, session_name: str | None = None
    ) -> None:
        self._repository.save_node_configuration(
            session_name=session_name,
            node_key=f"{manifest.id}:{manifest.version}",
            node_type=manifest.id,
            node_version=manifest.version,
            configuration_json=manifest.model_dump(mode="json"),
        )

    # -------------------------------------------------------------------------
    def _mask_configuration_secrets(
        self, payload: AppConfigurationPayload
    ) -> AppConfigurationPayload:
        sanitized = payload.model_copy(deep=True)
        sanitized.access_keys = [
            item.model_copy(
                update={"api_key": MASKED_API_KEY_VALUE if item.api_key else None}
            )
            for item in sanitized.access_keys
        ]
        return sanitized


configuration_service = ConfigurationService()
