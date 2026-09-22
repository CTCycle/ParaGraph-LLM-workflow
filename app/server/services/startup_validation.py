from __future__ import annotations

from server.services.configuration import configuration_service
from server.services.workflow import workflow_template_service

###############################################################################
def run_startup_validations() -> None:
    configuration_service.load_configuration()
    workflow_template_service.list_templates()
