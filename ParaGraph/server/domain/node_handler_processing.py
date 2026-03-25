from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _parse_json_value(value: Any, label: str) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc


class FixedSizeChunksParameters(BaseModel):
    chunk_size: int = Field(default=800, ge=1, le=100_000)
    chunk_overlap: int = Field(default=80, ge=0, le=99_999)
    unit: str = "words"

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"words", "characters"}:
            raise ValueError("unit must be one of: words, characters")
        return normalized

    @model_validator(mode="after")
    def validate_overlap(self) -> "FixedSizeChunksParameters":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class ByDelimiterChunksParameters(BaseModel):
    delimiter: str = "newline"
    keep_delimiter: bool = False
    drop_empty: bool = True
    max_chunk_size: int = Field(default=0, ge=0, le=100_000)
    overflow_strategy: str = "split_further"

    @field_validator("delimiter")
    @classmethod
    def validate_delimiter(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("delimiter must not be empty")
        return normalized

    @field_validator("overflow_strategy")
    @classmethod
    def validate_overflow_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"split_further", "discard", "emit_as_is"}:
            raise ValueError("overflow_strategy must be one of: split_further, discard, emit_as_is")
        return normalized


class ByStructureChunksParameters(BaseModel):
    strategy: str = "paragraph"
    max_chunk_size: int = Field(default=0, ge=0, le=100_000)
    chunk_overlap: int = Field(default=0, ge=0, le=99_999)
    unit: str = "words"
    overflow_strategy: str = "split_further"

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"paragraph", "section", "heading_and_content"}:
            raise ValueError("strategy must be one of: paragraph, section, heading_and_content")
        return normalized

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"words", "characters"}:
            raise ValueError("unit must be one of: words, characters")
        return normalized

    @field_validator("overflow_strategy")
    @classmethod
    def validate_overflow_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"split_further", "emit_as_is"}:
            raise ValueError("overflow_strategy must be one of: split_further, emit_as_is")
        return normalized


class RecursiveSplitChunksParameters(BaseModel):
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", " "])
    chunk_size: int = Field(default=800, ge=1, le=100_000)
    chunk_overlap: int = Field(default=80, ge=0, le=99_999)
    unit: str = "words"
    fallback_strategy: str = "continue"

    @field_validator("separators", mode="before")
    @classmethod
    def parse_separators(cls, value: Any) -> list[str]:
        parsed = _parse_json_value(value, "separators") if isinstance(value, str) else value
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("separators must be an array of strings")
        normalized = [item for item in (entry.strip() for entry in parsed) if item]
        if not normalized:
            raise ValueError("separators must include at least one value")
        return normalized

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"words", "characters"}:
            raise ValueError("unit must be one of: words, characters")
        return normalized

    @field_validator("fallback_strategy")
    @classmethod
    def validate_fallback_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"continue", "force_split"}:
            raise ValueError("fallback_strategy must be one of: continue, force_split")
        return normalized

    @model_validator(mode="after")
    def validate_overlap(self) -> "RecursiveSplitChunksParameters":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class SentenceWindowChunksParameters(BaseModel):
    sentences_per_chunk: int = Field(default=4, ge=1, le=1000)
    sentence_overlap: int = Field(default=1, ge=0, le=999)
    max_chunk_size: int = Field(default=0, ge=0, le=100_000)
    overflow_strategy: str = "split_further"

    @field_validator("overflow_strategy")
    @classmethod
    def validate_overflow_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"split_further", "emit_as_is"}:
            raise ValueError("overflow_strategy must be one of: split_further, emit_as_is")
        return normalized

    @model_validator(mode="after")
    def validate_overlap(self) -> "SentenceWindowChunksParameters":
        if self.sentence_overlap >= self.sentences_per_chunk:
            raise ValueError("sentence_overlap must be smaller than sentences_per_chunk")
        return self


class MergeSmallChunksParameters(BaseModel):
    target_chunk_size: int = Field(default=800, ge=1, le=100_000)
    unit: str = "words"
    max_chunk_size: int = Field(default=0, ge=0, le=100_000)
    merge_strategy: str = "sequential"
    preserve_boundaries: bool = True

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"words", "characters"}:
            raise ValueError("unit must be one of: words, characters")
        return normalized

    @field_validator("merge_strategy")
    @classmethod
    def validate_merge_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"sequential", "greedy"}:
            raise ValueError("merge_strategy must be one of: sequential, greedy")
        return normalized
