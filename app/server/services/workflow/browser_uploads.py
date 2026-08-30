from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from server.common import path as common_path


UPLOAD_ROOT = common_path.ARTIFACT_ROOT / "browser_uploads"


###############################################################################
class UploadedFile(Protocol):
    filename: str | None

    # -------------------------------------------------------------------------
    async def read(self, size: int = -1) -> bytes:
        raise NotImplementedError

    # -------------------------------------------------------------------------
    async def close(self) -> None:
        raise NotImplementedError


###############################################################################
class BrowserUploadService:
    # -------------------------------------------------------------------------
    def __init__(self, upload_root: Path) -> None:
        self._upload_root = upload_root

    # -------------------------------------------------------------------------
    def sanitize_relative_upload_path(self, file_name: str) -> Path:
        normalized = str(file_name or "").replace("\\", "/").strip()
        if not normalized:
            raise ValueError("Uploaded files must include a valid file name")

        candidate = PurePosixPath(normalized)
        if candidate.is_absolute():
            raise ValueError("Uploaded file names must not be absolute paths")

        parts = [part for part in candidate.parts if part not in ("", ".")]
        if not parts or any(part == ".." or ":" in part for part in parts):
            raise ValueError(
                "Uploaded file names must be relative paths inside the selected folder"
            )

        return Path(*parts)

    # -------------------------------------------------------------------------
    async def save_uploaded_directory(
        self, files: list[UploadedFile]
    ) -> tuple[str, int, list[str]]:
        if not files:
            raise ValueError("No files were provided for upload")

        destination_root = (self._upload_root / uuid4().hex).resolve()
        destination_root.mkdir(parents=True, exist_ok=True)

        saved_files = 0
        staged_files: list[str] = []
        try:
            for upload in files:
                relative_path = self.sanitize_relative_upload_path(
                    upload.filename or ""
                )
                destination = (destination_root / relative_path).resolve()
                try:
                    destination.relative_to(destination_root)
                except ValueError as exc:
                    raise ValueError(
                        "Uploaded file names must remain inside the staged folder"
                    ) from exc
                destination.parent.mkdir(parents=True, exist_ok=True)

                with destination.open("wb") as output_stream:
                    while True:
                        chunk = await upload.read(1024 * 1024)
                        if not chunk:
                            break
                        output_stream.write(chunk)

                saved_files += 1
                staged_files.append(str(destination.resolve()))
        finally:
            for upload in files:
                await upload.close()

        if saved_files == 0:
            raise ValueError("No files were uploaded")
        staged_files.sort()
        return str(destination_root), saved_files, staged_files


browser_upload_service = BrowserUploadService(UPLOAD_ROOT)
