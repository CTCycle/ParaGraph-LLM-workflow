from __future__ import annotations

from server.services.configuration import configuration_service
from server.services.workflow import node_registry, workflow_template_service


###############################################################################
def run_startup_validations() -> None:
    configuration_service.load_configuration()
    node_registry.reload()
    workflow_template_service.list_templates()
