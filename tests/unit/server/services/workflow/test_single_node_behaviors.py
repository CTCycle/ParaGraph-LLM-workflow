from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from starlette.datastructures import UploadFile

from ParaGraph.server.domain.workflowmodel import WorkflowDefinition
from ParaGraph.server.services.workflow.browser_uploads import save_uploaded_directory
from ParaGraph.server.services.workflow.compiler import compiler_service
from ParaGraph.server.services.workflow.execution import execution_service
from ParaGraph.server.services.workflow import browser_uploads as browser_uploads_module



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
    result = execution_service.execute_plan_job(plan=compiled.plan, workflow_id=None, job_id="run-single-node")
    run = execution_service.get_run("run-single-node")

    assert result == {"outputs": {}}
    assert run is not None
    assert run.status == "completed"
    assert run.outputs == {}
    assert run.steps[0].status == "completed"



def test_save_uploaded_directory_supports_single_uploaded_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(browser_uploads_module, "UPLOAD_ROOT", tmp_path / "browser_uploads")
    upload = UploadFile(filename="single/readme.txt", file=BytesIO(b"hello"))

    staged_root, file_count, files = asyncio.run(save_uploaded_directory([upload]))

    assert file_count == 1
    assert len(files) == 1
    staged_file = Path(files[0])
    assert staged_file.exists()
    assert staged_file.read_text(encoding="utf-8") == "hello"
    assert staged_file.is_relative_to(Path(staged_root))