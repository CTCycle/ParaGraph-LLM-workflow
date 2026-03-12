from __future__ import annotations

from ParaGraph.server.entities.configuration import (
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    OllamaStatusResponse,
)
from ParaGraph.server.entities.nodecatalog import NodeManifest
from ParaGraph.server.repositories.configuration import configuration_repository
from ParaGraph.server.services.llm.providers import OllamaClient, OllamaError


###############################################################################
class ConfigurationService:
    def load_configuration(self, session_name: str | None = None) -> AppConfigurationPayload:
        payload = configuration_repository.load_configuration(session_name=session_name)
        return AppConfigurationPayload.model_validate(payload)

    def save_configuration(self, payload: AppConfigurationPayload) -> AppConfigurationPayload:
        stored = configuration_repository.save_configuration(
            session_name=payload.session_name,
            access_keys=[item.model_dump(mode='json') for item in payload.access_keys],
            ollama=payload.ollama.model_dump(mode='json'),
        )
        return AppConfigurationPayload.model_validate(stored)

    def list_configuration_profiles(self, session_name: str | None = None) -> ConfigurationProfileListResponse:
        payload = configuration_repository.list_configuration_profiles(session_name=session_name)
        return ConfigurationProfileListResponse.model_validate(payload)

    def load_configuration_profile(self, *, session_name: str | None, profile_name: str) -> AppConfigurationPayload:
        profile_payload = configuration_repository.load_configuration_profile(
            session_name=session_name,
            profile_name=profile_name,
        )
        stored = configuration_repository.save_configuration(
            session_name=profile_payload['session_name'],
            access_keys=profile_payload.get('access_keys', []),
            ollama=profile_payload.get('ollama', {}),
        )
        return AppConfigurationPayload.model_validate(stored)

    def save_configuration_profile(
        self,
        *,
        profile_name: str,
        payload: AppConfigurationPayload,
    ) -> AppConfigurationPayload:
        stored = self.save_configuration(payload)
        configuration_repository.save_configuration_profile(
            session_name=stored.session_name,
            profile_name=profile_name,
            configuration_json=stored.model_dump(mode='json'),
        )
        return stored

    def ping_ollama(self, *, base_url: str | None, session_name: str | None = None) -> OllamaStatusResponse:
        resolved_base_url = base_url
        if not resolved_base_url:
            resolved_base_url = self.load_configuration(session_name=session_name).ollama.base_url

        try:
            models = OllamaClient(base_url=resolved_base_url).list_models()
            count = len(models)
            suffix = '' if count == 1 else 's'
            return OllamaStatusResponse(
                ok=True,
                message=f'Ollama reachable ({count} model{suffix} discovered).',
                base_url=resolved_base_url,
                model_count=count,
            )
        except (ValueError, OllamaError) as exc:
            return OllamaStatusResponse(
                ok=False,
                message=f'Ollama unreachable: {exc}',
                base_url=resolved_base_url,
                model_count=0,
            )

    def save_node_manifest(self, manifest: NodeManifest, session_name: str | None = None) -> None:
        configuration_repository.save_node_configuration(
            session_name=session_name,
            node_key=f'{manifest.id}:{manifest.version}',
            node_type=manifest.id,
            node_version=manifest.version,
            configuration_json=manifest.model_dump(mode='json'),
        )


configuration_service = ConfigurationService()
