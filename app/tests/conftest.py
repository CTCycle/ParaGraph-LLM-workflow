from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.common import path as common_path
from server.common.constants import DATABASE_FILENAME

_TEST_RESOURCES_TEMP = tempfile.TemporaryDirectory(
    prefix="paragraph-pytest-",
    dir=common_path.REPOSITORY_ROOT / "assets" / "QA",
)
_TEST_RESOURCES_ROOT = Path(_TEST_RESOURCES_TEMP.name).resolve()
_ORIGINAL_RESOURCES_ENV = os.environ.get(common_path.RESOURCES_ENV_KEY)
_ORIGINAL_PATHS = {
    name: getattr(common_path, name)
    for name in (
        "ENV_FILE",
        "RESOURCES_ROOT",
        "ARTIFACT_ROOT",
        "LOGS_ROOT",
        "MODELS_ROOT",
    )
}

os.environ[common_path.RESOURCES_ENV_KEY] = str(_TEST_RESOURCES_ROOT)
common_path.ENV_FILE = _TEST_RESOURCES_ROOT / "settings" / ".env"
common_path.ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
common_path.ENV_FILE.write_text(
    f'{common_path.RESOURCES_ENV_KEY}="{_TEST_RESOURCES_ROOT.as_posix()}"\n',
    encoding="utf-8",
)
_TEST_ENVIRONMENT_BASELINE = os.environ.copy()
common_path.RESOURCES_ROOT = common_path.resolve_resources_root()
if common_path.RESOURCES_ROOT.resolve() != _TEST_RESOURCES_ROOT:
    raise RuntimeError("Pytest resource root did not resolve to its isolated directory")
common_path.ARTIFACT_ROOT = common_path.RESOURCES_ROOT / "artifacts"
common_path.LOGS_ROOT = common_path.RESOURCES_ROOT / "logs"
common_path.MODELS_ROOT = common_path.RESOURCES_ROOT / "models"

_REPOSITORY_DATA_ROOT = common_path.REPOSITORY_ROOT / "data"
for _resource_name in ("nodes", "workflow_templates"):
    _source = _REPOSITORY_DATA_ROOT / _resource_name
    _destination = common_path.RESOURCES_ROOT / _resource_name
    if _source.is_dir():
        shutil.copytree(_source, _destination)
    else:
        _destination.mkdir(parents=True, exist_ok=True)

from server.app import app
from server.services.jobs import JobState
from server.repositories.database.initializer import initialize_database
from server.repositories.workflow import (
    database_chat_history_repository,
    execution_run_repository,
    in_memory_chat_history_repository,
    node_manifest_repository,
)
from server.services.jobs import job_manager
from server.services.runtime.events import execution_event_service
from server.services.workflow.nodes import registry as node_registry_module
from server.services.workflow.provider import provider_service

###############################################################################
@pytest.fixture(scope="session", autouse=True)
def initialized_application_database() -> Iterator[None]:
    database_path = (common_path.RESOURCES_ROOT / DATABASE_FILENAME).resolve()
    if not database_path.is_relative_to(_TEST_RESOURCES_ROOT):
        raise RuntimeError(f"Refusing to initialize non-test database: {database_path}")
    try:
        initialize_database()
        yield
    finally:
        from server.repositories.workflow.database import reset_database_engines

        reset_database_engines()
        from server.repositories.database.runtime import database_runtime

        database_runtime.reset_for_tests()
        root_logger = logging.getLogger()
        for handler in tuple(root_logger.handlers):
            if isinstance(handler, logging.FileHandler):
                log_path = Path(handler.baseFilename).resolve()
                if log_path.is_relative_to(_TEST_RESOURCES_ROOT):
                    root_logger.removeHandler(handler)
                    handler.close()
        for name, value in _ORIGINAL_PATHS.items():
            setattr(common_path, name, value)
        _TEST_RESOURCES_TEMP.cleanup()
        if _ORIGINAL_RESOURCES_ENV is None:
            os.environ.pop(common_path.RESOURCES_ENV_KEY, None)
        else:
            os.environ[common_path.RESOURCES_ENV_KEY] = _ORIGINAL_RESOURCES_ENV

###############################################################################
def clear_job_manager() -> None:
    job_manager.reset_for_tests()

###############################################################################
def clear_execution_state() -> None:
    execution_run_repository.reset_for_tests()
    execution_event_service.reset_for_tests()
    in_memory_chat_history_repository.reset_for_tests()
    database_chat_history_repository.reset_for_tests()

###############################################################################
def clear_provider_caches() -> None:
    provider_service.reset_for_tests()

###############################################################################
def restore_test_environment() -> None:
    pytest_environment = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("PYTEST_")
    }
    os.environ.clear()
    os.environ.update(_TEST_ENVIRONMENT_BASELINE)
    os.environ.update(pytest_environment)

###############################################################################
def register_job_state(
    job_id: str = "job-test", job_type: str = "workflow"
) -> JobState:
    state = JobState(job_id=job_id, job_type=job_type, status="running")
    job_manager.register_job_for_tests(state)
    return state

###############################################################################
def wait_for_job_completion(job_id: str, timeout_s: float = 2.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    last_snapshot: dict[str, object] | None = None

    while time.monotonic() < deadline:
        snapshot = job_manager.get_job_status(job_id)
        if snapshot is not None:
            last_snapshot = snapshot
            if str(snapshot["status"]) in {"completed", "failed", "cancelled"}:
                return snapshot
        time.sleep(0.01)

    raise AssertionError(
        f"Job {job_id} did not finish within {timeout_s} seconds. Last snapshot: {last_snapshot}"
    )

###############################################################################
@pytest.fixture(autouse=True)
def isolated_job_manager() -> Iterator[None]:
    clear_job_manager()
    yield
    clear_job_manager()

###############################################################################
@pytest.fixture(autouse=True)
def isolated_runtime_state() -> Iterator[None]:
    restore_test_environment()
    clear_execution_state()
    clear_provider_caches()

    try:
        yield
    finally:
        clear_execution_state()
        clear_provider_caches()
        restore_test_environment()

###############################################################################
@pytest.fixture(autouse=True)
def isolated_node_registry() -> Iterator[None]:
    default_node_root = common_path.RESOURCES_ROOT / "nodes"
    node_manifest_repository.configure_storage_for_tests(default_node_root)
    node_registry_module.node_registry.reload()
    try:
        yield
    finally:
        node_manifest_repository.restore_default_storage_for_tests()
        node_registry_module.node_registry.reload()

###############################################################################
@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client

###############################################################################
@pytest.fixture
def job_state_factory() -> Callable[[str, str], JobState]:
    return register_job_state

###############################################################################
@pytest.fixture
def wait_for_job() -> Callable[[str, float], dict[str, object]]:
    return wait_for_job_completion
