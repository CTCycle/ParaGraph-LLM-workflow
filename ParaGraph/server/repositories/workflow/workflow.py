from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.domain.workflow_model import (
    WorkflowDocument,
    WorkflowListItem,
)


class WorkflowRepository:
    def __init__(self) -> None:
        self._default_root = Path(RESOURCES_PATH) / "workflows"
        self._root = self._default_root
        self._index_path = self._root / "index.json"
        self._ensure_storage()

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

    def new_workflow_id(self) -> str:
        return f"wf_{uuid4().hex[:10]}"

    def save_workflow(self, document: WorkflowDocument) -> None:
        self._ensure_storage()
        workflow_dir = self._workflow_dir(document.workflow_id)
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = self._workflow_path(document.workflow_id)
        workflow_path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        self._upsert_index(document)

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

    def configure_storage_for_tests(self, root: Path) -> None:
        self._root = root
        self._index_path = self._root / "index.json"
        self._ensure_storage()

    def reset_for_tests(self) -> None:
        if self._root.exists():
            shutil.rmtree(self._root)
        self._ensure_storage()

    def restore_default_storage_for_tests(self) -> None:
        self._root = self._default_root
        self._index_path = self._root / "index.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def _workflow_dir(self, workflow_id: str) -> Path:
        return self._root / workflow_id

    def _workflow_path(self, workflow_id: str) -> Path:
        return self._workflow_dir(workflow_id) / "workflow.json"

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
