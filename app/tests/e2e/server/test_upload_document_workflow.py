from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

###############################################################################
def test_browser_uploaded_documents_complete_local_chunking_workflow(
    client: TestClient,
    tmp_path: Path,
    wait_for_job,
) -> None:
    """Validate the real upload API to deterministic document workflow boundary."""
    upload_response = client.post(
        "/nodes/uploads/directory",
        files=[
            (
                "files",
                ("dataset/readme.txt", b"Apples are crisp. Bananas are soft.", "text/plain"),
            ),
            (
                "files",
                (
                    "dataset/nested/notes.md",
                    b"Carrots are crunchy. Dates are sweet.",
                    "text/markdown",
                ),
            ),
        ],
    )
    assert upload_response.status_code == 200
    staged = upload_response.json()
    staged_root = Path(staged["path"])
    export_target = tmp_path / "exports" / "uploaded-chunks"

    try:
        assert staged["file_count"] == 2
        assert len(staged["files"]) == 2
        assert all(Path(path).is_file() for path in staged["files"])

        definition = {
            "schema_version": 2,
            "nodes": [
                {
                    "node_id": "load_1",
                    "node_type": "LOAD_DOCUMENTS",
                    "node_version": 1,
                    "parameters": {"folder_path": str(staged_root), "recursive": True},
                },
                {
                    "node_id": "extract_1",
                    "node_type": "DOCUMENT_TEXT_EXTRACTOR",
                    "node_version": 1,
                    "parameters": {"include_empty_pages": False},
                },
                {
                    "node_id": "chunk_1",
                    "node_type": "BY_DELIMITER_CHUNKS",
                    "node_version": 1,
                    "parameters": {
                        "delimiter": "period",
                        "keep_delimiter": False,
                        "drop_empty": True,
                        "max_chunk_size": 0,
                        "overflow_strategy": "split_further",
                    },
                },
                {
                    "node_id": "save_1",
                    "node_type": "SAVE_AS_FOLDER",
                    "node_version": 1,
                    "parameters": {
                        "output_path": str(export_target),
                        "extension": ".md",
                    },
                },
                {
                    "node_id": "output_1",
                    "node_type": "JSON_OUTPUT",
                    "node_version": 1,
                    "parameters": {},
                },
            ],
            "connections": [
                {
                    "from_node": "load_1",
                    "from_output": "documents",
                    "to_node": "extract_1",
                    "to_input": "documents",
                },
                {
                    "from_node": "extract_1",
                    "from_output": "documents",
                    "to_node": "chunk_1",
                    "to_input": "documents",
                },
                {
                    "from_node": "chunk_1",
                    "from_output": "chunks",
                    "to_node": "save_1",
                    "to_input": "chunks",
                },
                {
                    "from_node": "save_1",
                    "from_output": "artifact",
                    "to_node": "output_1",
                    "to_input": "value",
                },
            ],
            "metadata": {},
        }

        compiled_response = client.post(
            "/executions/compile", json={"definition": definition}
        )
        assert compiled_response.status_code == 200
        compiled = compiled_response.json()
        assert compiled["valid"] is True
        assert compiled["plan"] is not None

        started_response = client.post(
            "/executions",
            json={
                "workflow_id": "pg-t3-upload-documents",
                "execution_session_id": "pg-t3-upload-documents-session",
                "plan": compiled["plan"],
            },
        )
        assert started_response.status_code == 202
        run_id = started_response.json()["run_id"]

        status = wait_for_job(str(run_id), 5.0)
        run_response = client.get(f"/executions/{run_id}")
        assert run_response.status_code == 200
        run = run_response.json()
        assert status["status"] == "completed", run
        assert run["status"] == "completed", run

        steps = {step["node_id"]: step for step in run["steps"]}
        documents = steps["load_1"]["output"]["ports"]["documents"]
        assert len(documents) == 2
        assert {
            document["metadata"]["relative_path"] for document in documents
        } == {"dataset/readme.txt", "dataset/nested/notes.md"}
        assert all(Path(document["source_uri"]).is_file() for document in documents)

        extracted = steps["extract_1"]["output"]["ports"]["documents"]
        assert len(extracted) == 2
        assert all(document["metadata"]["document_id"] for document in extracted)

        artifact = run["outputs"]["output_1"]["json"]
        assert artifact["extension"] == ".md"
        assert artifact["count"] >= 4
        saved_files = [Path(path) for path in artifact["files"]]
        assert len(saved_files) == artifact["count"]
        assert all(path.is_file() and path.suffix == ".md" for path in saved_files)
        saved_text = "\n".join(path.read_text(encoding="utf-8") for path in saved_files)
        for phrase in (
            "Apples are crisp",
            "Bananas are soft",
            "Carrots are crunchy",
            "Dates are sweet",
        ):
            assert phrase in saved_text
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root, ignore_errors=True)
