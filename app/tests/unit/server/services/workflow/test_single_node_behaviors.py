from __future__ import annotations

import asyncio
import os
from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

from server.contracts.workflow_model import WorkflowDefinition
from server.services.workflow.browser_uploads import BrowserUploadService
from server.services.workflow.compiler import compiler_service
from server.services.workflow.execution import execution_service
from server.services.workflow import browser_uploads as browser_uploads_module

###############################################################################
def test_compiler_accepts_single_prompt_node_definition() -> None:
    definition = WorkflowDefinition.model_validate(
        {
            "schema_version": 2,
            "nodes": [
                {
                    "node_id": "prompt_1",
                    "node_type": "PROMPT",
                    "node_version": 1,
                    "parameters": {"prompt_text": "single node"},
                }
            ],
            "connections": [],
            "metadata": {},
        }
    )

    compiled = compiler_service.compile(definition)

    assert compiled.valid is True
    assert compiled.plan is not None
    assert compiled.plan.step_order == ["prompt_1"]
    assert compiled.plan.steps[0].node_type == "PROMPT"

###############################################################################
def test_execution_service_handles_single_non_output_step(job_state_factory) -> None:
    definition = WorkflowDefinition.model_validate(
        {
            "schema_version": 2,
            "nodes": [
                {
                    "node_id": "prompt_1",
                    "node_type": "PROMPT",
                    "node_version": 1,
                    "parameters": {"prompt_text": "single node"},
                }
            ],
            "connections": [],
            "metadata": {},
        }
    )
    compiled = compiler_service.compile(definition)
    assert compiled.plan is not None

    job_state_factory("run-single-node", "workflow")
    result = execution_service.execute_plan_job(
        plan=compiled.plan, workflow_id=None, job_id="run-single-node"
    )
    run = execution_service.get_run("run-single-node")

    assert result == {"outputs": {}}
    assert run is not None
    assert run.status == "completed"
    assert run.outputs == {}
    assert run.steps[0].status == "completed"

###############################################################################
def test_save_uploaded_directory_supports_single_uploaded_file(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        browser_uploads_module, "UPLOAD_ROOT", tmp_path / "browser_uploads"
    )
    upload = UploadFile(filename="single/readme.txt", file=BytesIO(b"hello"))
    service = BrowserUploadService(browser_uploads_module.UPLOAD_ROOT)

    staged_root, file_count, files = asyncio.run(
        service.save_uploaded_directory([upload])
    )

    assert file_count == 1
    assert len(files) == 1
    staged_file = Path(files[0])
    assert staged_file.exists()
    assert staged_file.read_text(encoding="utf-8") == "hello"
    assert staged_file.is_relative_to(Path(staged_root))

###############################################################################
def test_save_uploaded_directory_enforces_limits_and_cleans_partial_staging(
    tmp_path: Path,
) -> None:
    upload_root = tmp_path / "browser_uploads"
    service = BrowserUploadService(
        upload_root,
        max_files=1,
        max_file_bytes=4,
        max_total_bytes=4,
    )
    oversized = UploadFile(filename="too-large.txt", file=BytesIO(b"hello"))

    with pytest.raises(ValueError, match="size limit"):
        asyncio.run(service.save_uploaded_directory([oversized]))

    assert list(upload_root.iterdir()) == []

###############################################################################
def test_save_uploaded_directory_removes_staging_after_later_file_failure(
    tmp_path: Path,
) -> None:
    class FailingUpload:
        filename = "broken.txt"

        async def read(self, size: int = -1) -> bytes:
            raise RuntimeError("read failed")

        async def close(self) -> None:
            return None

    upload_root = tmp_path / "browser_uploads"
    service = BrowserUploadService(upload_root)
    good = UploadFile(filename="good.txt", file=BytesIO(b"good"))

    with pytest.raises(RuntimeError, match="read failed"):
        asyncio.run(service.save_uploaded_directory([good, FailingUpload()]))

    assert list(upload_root.iterdir()) == []

###############################################################################
def test_cleanup_stale_uploads_removes_only_expired_directories(tmp_path: Path) -> None:
    upload_root = tmp_path / "browser_uploads"
    stale = upload_root / "stale"
    fresh = upload_root / "fresh"
    stale.mkdir(parents=True)
    fresh.mkdir()
    os.utime(stale, (0, 0))

    service = BrowserUploadService(upload_root, staging_retention_seconds=10)
    service.cleanup_stale_uploads(now=20)

    assert not stale.exists()
    assert fresh.exists()
