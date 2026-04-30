from __future__ import annotations

from pathlib import Path

import httpx

from server.services.workflow.provider import (
    huggingface_downloads as huggingface_downloads_module,
)
from server.services.workflow.provider import (
    huggingface_catalog as huggingface_catalog_module,
)
from server.services.workflow.provider import (
    HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS,
    ProviderService,
)
from server.services.workflow.provider.constants import (
    HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS,
    HUGGINGFACE_FALLBACK_LIBRARIES,
    HUGGINGFACE_FALLBACK_TASKS,
)


class _FakeExpandApi:
    def list_models(
        self,
        *,
        search: str | None = None,
        author: str | None = None,
        pipeline_tag: str | None = None,
        library: str | None = None,
        filter: str | list[str] | None = None,
        sort: str | None = None,
        direction: int | None = None,
        gated: bool | None = None,
        expand: list[str] | None = None,
        full: bool | None = None,
        limit: int | None = None,
        token: str | None = None,
    ) -> None:
        return None


def test_build_huggingface_list_kwargs_prefers_expand() -> None:
    service = ProviderService()

    kwargs = service._build_huggingface_list_kwargs(  # noqa: SLF001
        _FakeExpandApi(),
        token="hf_test",
        search="qwen",
        task="text-generation",
        library="transformers",
        author="Qwen",
        visibility="public",
        sort="downloads",
        limit=10,
    )

    assert kwargs["expand"] == list(HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS)
    assert "full" not in kwargs


def test_huggingface_download_uses_explicit_stream_timeout(
    monkeypatch, tmp_path: Path, job_state_factory
) -> None:
    service = ProviderService()
    destination = tmp_path / "huggingface"
    files = [{"path": "model.bin", "size": 4}]
    capture: dict[str, object] = {}

    class _FakeResponse:
        headers = {"Content-Length": "4"}

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self, chunk_size: int = 0):
            _ = chunk_size
            yield b"data"

    class _FakeStreamContext:
        def __enter__(self) -> _FakeResponse:
            return _FakeResponse()

        def __exit__(self, exc_type, exc, tb) -> bool:
            _ = (exc_type, exc, tb)
            return False

    def _fake_stream(method: str, url: str, **kwargs):
        _ = (method, url)
        capture["timeout"] = kwargs.get("timeout")
        return _FakeStreamContext()

    monkeypatch.setattr(
        huggingface_downloads_module,
        "hf_hub_url",
        lambda **kwargs: "https://example.invalid/model.bin",
    )
    monkeypatch.setattr(huggingface_downloads_module.httpx, "stream", _fake_stream)
    job_state_factory("job-timeout", "huggingface_download")

    result = service._run_huggingface_download_job(  # noqa: SLF001
        job_id="job-timeout",
        repo_id="owner/model",
        destination_path=str(destination),
        files=files,
        total_bytes=4,
        revision="main",
        token=None,
    )

    assert result["downloaded_bytes"] == 4
    assert isinstance(capture["timeout"], httpx.Timeout)
    timeout = capture["timeout"]
    assert timeout.connect == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout.read == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout.write == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout.pool == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS


def test_huggingface_filter_tags_logs_and_falls_back(monkeypatch) -> None:
    service = ProviderService()
    captured: list[dict[str, object]] = []

    class _FailingApi:
        def get_model_tags(self) -> dict[str, object]:
            raise RuntimeError("tag service unavailable")

    def _capture_warning(message: str, *args, **kwargs) -> None:
        captured.append({"message": message, "args": args, "kwargs": kwargs})

    monkeypatch.setattr(huggingface_catalog_module.logger, "warning", _capture_warning)
    tasks, libraries = service._load_huggingface_filter_tags(  # noqa: SLF001
        api=_FailingApi(),
        token="hf_secret",
        refresh=True,
    )

    assert tasks == HUGGINGFACE_FALLBACK_TASKS
    assert libraries == HUGGINGFACE_FALLBACK_LIBRARIES
    assert captured
    assert captured[0]["kwargs"].get("exc_info") is True

