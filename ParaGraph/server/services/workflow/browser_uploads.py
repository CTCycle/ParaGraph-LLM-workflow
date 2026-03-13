from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import UploadFile


UPLOAD_ROOT = Path("ParaGraph/resources/artifacts/browser_uploads")


def _sanitize_relative_upload_path(file_name: str) -> Path:
    normalized = str(file_name or "").replace("\\", "/").strip()
    if not normalized:
        raise ValueError("Uploaded files must include a valid file name")

    candidate = PurePosixPath(normalized)
    parts = [part for part in candidate.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Uploaded file names must be relative paths inside the selected folder")

    return Path(*parts)


async def save_uploaded_directory(files: list[UploadFile]) -> tuple[str, int]:
    if not files:
        raise ValueError("No files were provided for upload")

    destination_root = (UPLOAD_ROOT / uuid4().hex).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)

    saved_files = 0
    try:
        for upload in files:
            relative_path = _sanitize_relative_upload_path(upload.filename or "")
            destination = destination_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)

            with destination.open("wb") as output_stream:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    output_stream.write(chunk)

            saved_files += 1
    finally:
        for upload in files:
            await upload.close()

    if saved_files == 0:
        raise ValueError("No files were uploaded")
    return str(destination_root), saved_files
