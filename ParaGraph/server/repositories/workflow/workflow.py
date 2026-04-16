from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.domain.workflow_model import (
    VisualGraph,
    WorkflowDefinition,
    WorkflowDocument,
    WorkflowListItem,
)


class WorkflowRepository:
    def __init__(self) -> None:
        self._root = Path(RESOURCES_PATH) / "workflows"
        self._index_path = self._root / "index.json"
        self._root.mkdir(parents=True, exist_ok=True)

    def list_workflows(self) -> list[WorkflowListItem]:
        index = self._load_index()
        items: list[WorkflowListItem] = []
        for item in index:
            updated_at = datetime.fromisoformat(str(item["updated_at"]))
            items.append(
                WorkflowListItem(
                    workflow_id=str(item["workflow_id"]),
                    name=str(item["name"]),
                    updated_at=updated_at,
                )
            )
        return sorted(items, key=lambda entry: entry.updated_at, reverse=True)

    def create_workflow(
        self,
        *,
        name: str,
        definition: WorkflowDefinition,
        visual_graph: VisualGraph,
    ) -> WorkflowDocument:
        workflow_id = f"wf_{uuid4().hex[:10]}"
        document = WorkflowDocument(
            workflow_id=workflow_id,
            name=name,
            definition=definition,
            visual_graph=visual_graph,
        )
        self._save_document(document)
        self._upsert_index(document)
        return document

    def update_workflow(
        self,
        *,
        workflow_id: str,
        name: str | None,
        definition: WorkflowDefinition,
        visual_graph: VisualGraph,
    ) -> WorkflowDocument | None:
        current = self.get_workflow(workflow_id)
        if current is None:
            return None

        document = WorkflowDocument(
            workflow_id=workflow_id,
            name=name or current.name,
            definition=definition,
            visual_graph=visual_graph,
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._save_document(document)
        self._upsert_index(document)
        return document

    def get_workflow(self, workflow_id: str) -> WorkflowDocument | None:
        index = self._load_index()
        entry = next(
            (item for item in index if item["workflow_id"] == workflow_id), None
        )
        if entry is None:
            return None
        path = self._workflow_path(workflow_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowDocument.model_validate(payload)

    def _workflow_dir(self, workflow_id: str) -> Path:
        return self._root / workflow_id

    def _workflow_path(self, workflow_id: str) -> Path:
        return self._workflow_dir(workflow_id) / "workflow.json"

    def _save_document(self, document: WorkflowDocument) -> None:
        workflow_dir = self._workflow_dir(document.workflow_id)
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = self._workflow_path(document.workflow_id)
        workflow_path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_path.exists():
            return []
        payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _save_index(self, entries: list[dict[str, Any]]) -> None:
        self._index_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _upsert_index(self, document: WorkflowDocument) -> None:
        entries = self._load_index()
        serialized = {
            "workflow_id": document.workflow_id,
            "name": document.name,
            "updated_at": document.updated_at.isoformat(),
        }

        replaced = False
        for idx, entry in enumerate(entries):
            if entry.get("workflow_id") == document.workflow_id:
                entries[idx] = serialized
                replaced = True
                break
        if not replaced:
            entries.append(serialized)

        self._save_index(entries)


workflow_repository = WorkflowRepository()
