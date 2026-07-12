from __future__ import annotations

from typing import Any

from pytest import MonkeyPatch

from server.services.workflow import node_registry
from server.services.workflow.node_handlers.core import routing

###############################################################################
class FakeTokenizer:

    # -------------------------------------------------------------------------
    def __call__(self, text: str, **_: Any) -> dict[str, list[int]]:
        return {
            "input_ids": [len(text), 101],
            "attention_mask": [1, 1],
            "token_type_ids": [0, 0],
        }

###############################################################################
class FakeAutoTokenizer:

    # -------------------------------------------------------------------------
    @staticmethod
    def from_pretrained(_: str, **__: Any) -> FakeTokenizer:
        return FakeTokenizer()

###############################################################################
def test_tokenizer_returns_structured_output_only(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(routing, "AutoTokenizer", FakeAutoTokenizer)

    result = node_registry.execute(
        "TOKENIZER",
        2,
        {
            "tokenizer_name": "fake-tokenizer",
            "output_format": "json",
            "return_attention_mask": True,
            "return_token_type_ids": True,
        },
        {"text": "hello"},
    )

    assert set(result) == {"tokenized"}
    assert result["tokenized"]["records"][0]["token_ids"] == [5, 101]

###############################################################################
def test_tokenizer_returns_serialized_output_only(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(routing, "AutoTokenizer", FakeAutoTokenizer)

    result = node_registry.execute(
        "TOKENIZER",
        2,
        {"tokenizer_name": "fake-tokenizer", "output_format": "string"},
        {"text": "hello"},
    )

    assert set(result) == {"serialized"}
