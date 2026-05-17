from __future__ import annotations

from server.services.workflow.node_handlers.common import (
    coerce_float,
    coerce_json_object,
    extract_top_level_json_fields,
    parse_json_if_possible,
)


def test_json_object_parsing_from_dict_and_string() -> None:
    assert coerce_json_object({"summary": "ok"}) == {"summary": "ok"}
    assert coerce_json_object('{"summary": "ok"}') == {"summary": "ok"}


def test_non_object_json_does_not_expose_top_level_fields() -> None:
    assert extract_top_level_json_fields("[1, 2]") == {}


def test_invalid_json_returns_original_text_where_required() -> None:
    assert parse_json_if_possible("{bad json") == "{bad json"


def test_coerce_float_handles_invalid_value() -> None:
    assert coerce_float("not-a-number", 1.5) == 1.5
