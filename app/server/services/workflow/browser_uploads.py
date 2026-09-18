from __future__ import annotations

import shutil
import time
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from server.common import path as common_path


UPLOAD_ROOT = common_path.ARTIFACT_ROOT / "browser_uploads"
DEFAULT_MAX_UPLOAD_FILES = 1000
DEFAULT_MAX_UPLOAD_FILE_BYTES = 100_000_000
DEFAULT_MAX_UPLOAD_TOTAL_BYTES = 1_000_000_000
DEFAULT_STAGING_RETENTION_SECONDS = 24 * 60 * 60

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
    def __init__(
        self,
        upload_root: Path,
        *,
        max_files: int = DEFAULT_MAX_UPLOAD_FILES,
        max_file_bytes: int = DEFAULT_MAX_UPLOAD_FILE_BYTES,
        max_total_bytes: int = DEFAULT_MAX_UPLOAD_TOTAL_BYTES,
        staging_retention_seconds: float = DEFAULT_STAGING_RETENTION_SECONDS,
    ) -> None:
        if max_files < 1 or max_file_bytes < 1 or max_total_bytes < 1:
            raise ValueError("Upload limits must be positive")
        if staging_retention_seconds <= 0:
            raise ValueError("Staging retention must be positive")
        self._upload_root = upload_root
        self._max_files = max_files
        self._max_file_bytes = max_file_bytes
        self._max_total_bytes = max_total_bytes
        self._staging_retention_seconds = staging_retention_seconds

    # -------------------------------------------------------------------------
    def cleanup_stale_uploads(self, *, now: float | None = None) -> None:
        if not self._upload_root.exists():
            return
        cutoff = (time.time() if now is None else now) - self._staging_retention_seconds
        for entry in self._upload_root.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry)
            except FileNotFoundError:
                continue

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
        if len(files) > self._max_files:
            raise ValueError(
                f"Uploads may contain at most {self._max_files} files"
            )

        self.cleanup_stale_uploads()
        destination_root = (self._upload_root / uuid4().hex).resolve()
        destination_root.mkdir(parents=True, exist_ok=True)

        saved_files = 0
        total_bytes = 0
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

                file_bytes = 0
                with destination.open("wb") as output_stream:
                    while True:
                        chunk = await upload.read(1024 * 1024)
                        if not chunk:
                            break
                        file_bytes += len(chunk)
                        total_bytes += len(chunk)
                        if file_bytes > self._max_file_bytes:
                            raise ValueError(
                                "Uploaded file exceeds the configured size limit"
                            )
                        if total_bytes > self._max_total_bytes:
                            raise ValueError(
                                "Uploaded directory exceeds the configured size limit"
                            )
                        output_stream.write(chunk)

                saved_files += 1
                staged_files.append(str(destination.resolve()))
        except BaseException:
            shutil.rmtree(destination_root, ignore_errors=True)
            raise
        finally:
            for upload in files:
                await upload.close()

        if saved_files == 0:
            raise ValueError("No files were uploaded")
        staged_files.sort()
        return str(destination_root), saved_files, staged_files


browser_upload_service = BrowserUploadService(UPLOAD_ROOT)
