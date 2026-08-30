from __future__ import annotations

import json
import shutil
from pathlib import Path

from server.common import path as common_path
from server.contracts.chat_history import ChatHistoryMessage


###############################################################################
def _safe_segment(value: str) -> str:
    normalized = "".join(
        char for char in value.strip() if char.isalnum() or char in {"-", "_", "."}
    )
    return normalized or "default"


###############################################################################
class FileChatHistoryRepository:
    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        self._default_root = common_path.RESOURCES_ROOT / "chat_history"
        self._root = self._default_root
        self._ensure_root()

    # -------------------------------------------------------------------------
    def _ensure_root(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    def _file_path(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> Path:
        safe_workflow_id = _safe_segment(workflow_id)
        safe_session_id = _safe_segment(execution_session_id)
        safe_node_id = _safe_segment(node_id)
        return self._root / safe_workflow_id / safe_session_id / f"{safe_node_id}.json"

    # -------------------------------------------------------------------------
    def get_messages(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> list[ChatHistoryMessage]:
        path = self._file_path(workflow_id, execution_session_id, node_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return []
        messages: list[ChatHistoryMessage] = []
        for item in payload:
            if isinstance(item, dict):
                messages.append(ChatHistoryMessage.model_validate(item))
        return messages

    # -------------------------------------------------------------------------
    def append_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> list[ChatHistoryMessage]:
        current = self.get_messages(workflow_id, execution_session_id, node_id)
        current.extend(item.model_copy(deep=True) for item in messages)

        path = self._file_path(workflow_id, execution_session_id, node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in current],
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        return current

    # -------------------------------------------------------------------------
    def set_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> None:
        path = self._file_path(workflow_id, execution_session_id, node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in messages],
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------------------
    def clear_messages(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> None:
        path = self._file_path(workflow_id, execution_session_id, node_id)
        path.unlink(missing_ok=True)
        for parent in (path.parent, path.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                break

    # -------------------------------------------------------------------------
    def clear_session(self, workflow_id: str, execution_session_id: str) -> None:
        session_path = (
            self._root
            / _safe_segment(workflow_id)
            / _safe_segment(execution_session_id)
        )
        if session_path.exists():
            shutil.rmtree(session_path)

    # -------------------------------------------------------------------------
    def configure_storage_for_tests(self, root: Path) -> None:
        self._root = root
        self._ensure_root()

    # -------------------------------------------------------------------------
    def restore_default_storage_for_tests(self) -> None:
        self._root = self._default_root
        self._ensure_root()

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        if self._root.exists():
            shutil.rmtree(self._root)
        self._ensure_root()


file_chat_history_repository = FileChatHistoryRepository()
