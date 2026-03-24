from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.domain.workflowmodel import (
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
                    latest_version=int(item["latest_version"]),
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
            latest_version=1,
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
        current = self.get_latest_workflow(workflow_id)
        if current is None:
            return None

        document = WorkflowDocument(
            workflow_id=workflow_id,
            name=name or current.name,
            latest_version=current.latest_version + 1,
            definition=definition,
            visual_graph=visual_graph,
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._save_document(document)
        self._upsert_index(document)
        return document

    def get_latest_workflow(self, workflow_id: str) -> WorkflowDocument | None:
        index = self._load_index()
        entry = next((item for item in index if item["workflow_id"] == workflow_id), None)
        if entry is None:
            return None
        return self.get_workflow_version(workflow_id, int(entry["latest_version"]))

    def get_workflow_version(self, workflow_id: str, version: int) -> WorkflowDocument | None:
        path = self._version_path(workflow_id, version)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowDocument.model_validate(payload)

    def list_versions(self, workflow_id: str) -> list[int]:
        workflow_dir = self._workflow_dir(workflow_id)
        if not workflow_dir.exists():
            return []
        versions: list[int] = []
        for path in workflow_dir.glob("v*.json"):
            raw = path.stem.removeprefix("v")
            if raw.isdigit():
                versions.append(int(raw))
        return sorted(versions)

    def _workflow_dir(self, workflow_id: str) -> Path:
        return self._root / workflow_id

    def _version_path(self, workflow_id: str, version: int) -> Path:
        return self._workflow_dir(workflow_id) / f"v{version}.json"

    def _save_document(self, document: WorkflowDocument) -> None:
        workflow_dir = self._workflow_dir(document.workflow_id)
        workflow_dir.mkdir(parents=True, exist_ok=True)
        version_path = self._version_path(document.workflow_id, document.latest_version)
        version_path.write_text(
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
            "latest_version": document.latest_version,
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