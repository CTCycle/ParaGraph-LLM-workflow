from __future__ import annotations

import json
from pathlib import Path

from server.common import path as common_path
from server.contracts.node_catalog import NodeManifest


###############################################################################
class NodeManifestRepository:
    # -------------------------------------------------------------------------
    def __init__(self, root: Path | None = None) -> None:
        self._default_root = common_path.RESOURCES_ROOT / "nodes"
        self._root = root or self._default_root
        self._ensure_storage()

    # -------------------------------------------------------------------------
    @property
    def root(self) -> Path:
        return self._root

    # -------------------------------------------------------------------------
    def list_manifest_files(self) -> list[Path]:
        self._ensure_storage()
        return sorted(self._root.glob("*.json"))

    # -------------------------------------------------------------------------
    def load_manifest(self, path: Path) -> NodeManifest:
        return NodeManifest.model_validate_json(path.read_text(encoding="utf-8"))

    # -------------------------------------------------------------------------
    def path_for_manifest(self, manifest: NodeManifest) -> Path:
        filename = f"{manifest.id.lower()}_v{manifest.version}.json"
        return self._root / filename

    # -------------------------------------------------------------------------
    def save_manifest(self, manifest: NodeManifest) -> Path:
        self._ensure_storage()
        path = self.path_for_manifest(manifest)
        path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return path

    # -------------------------------------------------------------------------
    def delete_manifest(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    # -------------------------------------------------------------------------
    def configure_storage_for_tests(self, root: Path) -> None:
        self._root = root
        self._ensure_storage()

    # -------------------------------------------------------------------------
    def restore_default_storage_for_tests(self) -> None:
        self._root = self._default_root
        self._ensure_storage()

    # -------------------------------------------------------------------------
    def _ensure_storage(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)


node_manifest_repository = NodeManifestRepository()
