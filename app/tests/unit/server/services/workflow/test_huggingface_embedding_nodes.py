from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from server.services.workflow.node_handlers import core as core_module


###############################################################################
def test_huggingface_embedding_uses_eos_token_when_tokenizer_has_no_pad_token(
    monkeypatch,
) -> None:
    core_module._HF_EMBEDDING_CACHE.clear()  # noqa: SLF001

    ###############################################################################
    class FakeTokenizer:
        pad_token = None
        eos_token = "<eos>"

        # -------------------------------------------------------------------------
        def __call__(self, texts, *, padding, truncation, return_tensors):
            assert texts == ["hello"]
            assert padding is True
            assert truncation is True
            assert return_tensors == "pt"
            assert self.pad_token == self.eos_token
            return {
                "input_ids": torch.tensor([[1, 2]]),
                "attention_mask": torch.tensor([[1, 1]]),
            }

    fake_tokenizer = FakeTokenizer()

    ###############################################################################
    class FakeAutoTokenizer:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            assert model_name == "fake-embedding-model"
            assert token is None
            return fake_tokenizer

    ###############################################################################
    class FakeModel:
        device = None

        # -------------------------------------------------------------------------
        def __call__(self, **kwargs):
            assert "input_ids" in kwargs
            return SimpleNamespace(
                last_hidden_state=torch.tensor([[[1.0, 2.0], [3.0, 4.0]]])
            )

    ###############################################################################
    class FakeAutoModel:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            assert model_name == "fake-embedding-model"
            assert token is None
            return FakeModel()

    monkeypatch.setattr(
        core_module.configuration_service,
        "load_configuration",
        lambda: SimpleNamespace(access_keys=[]),
    )
    monkeypatch.setattr(
        core_module,
        "_load_huggingface_embedding_modules",
        lambda: (torch, FakeAutoModel, FakeAutoTokenizer),
    )

    vector = core_module._embed_text_with_huggingface(  # noqa: SLF001
        model_name="fake-embedding-model",
        text="hello",
    )

    assert fake_tokenizer.pad_token == fake_tokenizer.eos_token
    assert len(vector) == 2
    assert sum(item * item for item in vector) == pytest.approx(1.0, abs=1e-6)


###############################################################################
def test_huggingface_embedding_can_use_explicit_tokenizer_repo(monkeypatch) -> None:
    core_module._HF_EMBEDDING_CACHE.clear()  # noqa: SLF001
    captured: dict[str, str] = {}

    ###############################################################################
    class FakeTokenizer:
        pad_token = "<pad>"
        eos_token = "<eos>"

        # -------------------------------------------------------------------------
        def __call__(self, texts, *, padding, truncation, return_tensors):
            _ = (texts, padding, truncation, return_tensors)
            return {
                "input_ids": torch.tensor([[1]]),
                "attention_mask": torch.tensor([[1]]),
            }

    ###############################################################################
    class FakeAutoTokenizer:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            _ = token
            captured["tokenizer"] = model_name
            return FakeTokenizer()

    ###############################################################################
    class FakeModel:
        device = None

        # -------------------------------------------------------------------------
        def __call__(self, **kwargs):
            _ = kwargs
            return SimpleNamespace(last_hidden_state=torch.tensor([[[1.0, 0.0]]]))

    ###############################################################################
    class FakeAutoModel:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            _ = token
            captured["model"] = model_name
            return FakeModel()

    monkeypatch.setattr(
        core_module.configuration_service,
        "load_configuration",
        lambda: SimpleNamespace(access_keys=[]),
    )
    monkeypatch.setattr(
        core_module,
        "_load_huggingface_embedding_modules",
        lambda: (torch, FakeAutoModel, FakeAutoTokenizer),
    )

    vector = core_module._embed_text_with_huggingface(  # noqa: SLF001
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_name="bert-base-uncased",
        text="hello",
    )

    assert captured == {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "tokenizer": "bert-base-uncased",
    }
    assert vector == [1.0, 0.0]
