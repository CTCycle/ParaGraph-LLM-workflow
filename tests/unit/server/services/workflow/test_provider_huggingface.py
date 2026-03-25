from __future__ import annotations

from ParaGraph.server.services.workflow.provider import (
    HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS,
    ProviderService,
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


class _FakeLegacyApi:
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
        full: bool | None = None,
        limit: int | None = None,
        token: str | None = None,
    ) -> None:
        return None


def test_build_huggingface_list_kwargs_prefers_expand() -> None:
    service = ProviderService()

    kwargs = service._build_huggingface_list_kwargs(  # noqa: SLF001
        _FakeExpandApi(),
        token='hf_test',
        search='qwen',
        task='text-generation',
        library='transformers',
        author='Qwen',
        visibility='public',
        sort='downloads',
        limit=10,
    )

    assert kwargs['expand'] == list(HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS)
    assert 'full' not in kwargs


def test_build_huggingface_list_kwargs_falls_back_to_full_for_legacy_signature() -> None:
    service = ProviderService()

    kwargs = service._build_huggingface_list_kwargs(  # noqa: SLF001
        _FakeLegacyApi(),
        token='hf_test',
        search='qwen',
        task='text-generation',
        library='transformers',
        author='Qwen',
        visibility='public',
        sort='downloads',
        limit=10,
    )

    assert kwargs['full'] is True
    assert 'expand' not in kwargs
