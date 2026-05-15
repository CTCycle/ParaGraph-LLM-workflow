from __future__ import annotations

from pathlib import Path

from server.common.constants import RESOURCES_PATH
from server.domain.workflow_templates import (
    WorkflowTemplateListResponse,
    WorkflowTemplateManifest,
)
from server.services.workflow.compiler import compiler_service
from server.services.workflow.nodes import node_registry


TEMPLATE_ROOT = Path(RESOURCES_PATH) / "workflow_templates"


class WorkflowTemplateService:
    def __init__(self) -> None:
        TEMPLATE_ROOT.mkdir(parents=True, exist_ok=True)

    def _load_template(self, path: Path) -> WorkflowTemplateManifest:
        template = WorkflowTemplateManifest.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        self._validate_required_nodes(template)
        self._validate_compilation(template)
        return template

    def _validate_required_nodes(self, template: WorkflowTemplateManifest) -> None:
        missing: list[str] = []
        for manifest in template.required_nodes:
            exists = node_registry.get(manifest.id, manifest.version)
            if exists is None:
                missing.append(f"{manifest.id} v{manifest.version}")
        if missing:
            raise ValueError(
                f"Template '{template.id}' references missing node manifests: {', '.join(sorted(missing))}"
            )

    def _validate_compilation(self, template: WorkflowTemplateManifest) -> None:
        result = compiler_service.compile(template.definition)
        if result.valid:
            return
        if not result.diagnostics:
            raise ValueError(
                f"Template '{template.id}' failed compilation without diagnostics"
            )
        preview = "; ".join(diagnostic.message for diagnostic in result.diagnostics[:3])
        if len(result.diagnostics) > 3:
            preview = f"{preview}; (+{len(result.diagnostics) - 3} more)"
        raise ValueError(f"Template '{template.id}' failed compilation: {preview}")

    def list_templates(self) -> WorkflowTemplateListResponse:
        templates: list[WorkflowTemplateManifest] = []
        seen_ids: set[str] = set()

        for path in sorted(TEMPLATE_ROOT.glob("*.json")):
            template = self._load_template(path)
            normalized_id = template.id.strip().lower()
            if normalized_id in seen_ids:
                raise ValueError(f"Duplicate workflow template id: {template.id}")
            seen_ids.add(normalized_id)
            templates.append(template)

        return WorkflowTemplateListResponse(templates=templates)


workflow_template_service = WorkflowTemplateService()

