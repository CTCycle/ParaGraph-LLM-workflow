from __future__ import annotations

from ParaGraph.server.entities.configuration import AppConfigurationPayload
from ParaGraph.server.entities.nodecatalog import NodeManifest
from ParaGraph.server.repositories.configuration import configuration_repository


###############################################################################
class ConfigurationService:
    def load_configuration(self, session_name: str | None = None) -> AppConfigurationPayload:
        payload = configuration_repository.load_configuration(session_name=session_name)
        return AppConfigurationPayload.model_validate(payload)

    def save_configuration(self, payload: AppConfigurationPayload) -> AppConfigurationPayload:
        stored = configuration_repository.save_configuration(
            session_name=payload.session_name,
            access_keys=[item.model_dump(mode="json") for item in payload.access_keys],
            ollama=payload.ollama.model_dump(mode="json"),
        )
        return AppConfigurationPayload.model_validate(stored)

    def save_node_manifest(self, manifest: NodeManifest, session_name: str | None = None) -> None:
        configuration_repository.save_node_configuration(
            session_name=session_name,
            node_key=f"{manifest.id}:{manifest.version}",
            node_type=manifest.id,
            node_version=manifest.version,
            configuration_json=manifest.model_dump(mode="json"),
        )


configuration_service = ConfigurationService()
