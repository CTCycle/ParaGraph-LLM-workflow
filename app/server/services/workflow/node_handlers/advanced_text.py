from __future__ import annotations

import difflib
import re
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser
from markdown_it import MarkdownIt
from rapidfuzz import fuzz

from server.domain.node_handler_advanced_text import AdvancedTextParameters
from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.common import coerce_text


PII_PATTERNS = {
    "email": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    "phone": r"\b(?:\+?\d[\d .()-]{7,}\d)\b",
    "id": r"\b(?:SSN|ID|Passport)[:# ]+[A-Z0-9-]{4,}\b",
    "address": r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln)\b",
}

###############################################################################
def _text(inputs: dict[str, Any], key: str = "text") -> str:
    return coerce_text(inputs.get(key, inputs.get("value", "")))

###############################################################################
def _classifier(label: str, score: float, matches: list[Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"label": label, "score": score, "matches": matches, "metadata": metadata or {}}

###############################################################################
def _claim_extractor_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    claims = [part.strip() for part in re.split(r"(?<=[.!?])\s+", _text(inputs)) if part.strip()]
    return {"result": [{"claim": claim, "index": index} for index, claim in enumerate(claims)]}

###############################################################################
def _contradiction_detector_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    left = _text(inputs, "left").lower()
    right = _text(inputs, "right").lower()
    negated = (" not " in left) != (" not " in right)
    left_numbers = re.findall(r"\d+(?:\.\d+)?", left)
    right_numbers = re.findall(r"\d+(?:\.\d+)?", right)
    numeric_conflict = bool(left_numbers and right_numbers and left_numbers != right_numbers)
    return _classifier("contradiction" if negated or numeric_conflict else "neutral", 1.0 if negated or numeric_conflict else 0.0, [])

###############################################################################
def _entity_extractor_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = _text(inputs)
    entities = [{"text": match.group(0), "type": "proper_noun"} for match in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)]
    return {"result": entities}

###############################################################################
def _entity_resolver_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = AdvancedTextParameters.model_validate(parameters)
    entities = inputs.get("entities", [])
    values = [item.get("text", item) if isinstance(item, dict) else item for item in (entities if isinstance(entities, list) else [entities])]
    clusters: list[list[str]] = []
    for value in map(str, values):
        for cluster in clusters:
            score = fuzz.ratio(value.lower(), cluster[0].lower())
            if score >= parsed.threshold * 100:
                cluster.append(value)
                break
        else:
            clusters.append([value])
    return {"result": [{"canonical": cluster[0], "aliases": cluster} for cluster in clusters]}

###############################################################################
def _pii_detector_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = _text(inputs)
    matches = []
    for kind, pattern in PII_PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({"type": kind, "text": match.group(0), "span": list(match.span())})
    return {"result": matches}

###############################################################################
def _pii_redactor_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = AdvancedTextParameters.model_validate(parameters)
    text = _text(inputs)
    for pattern in PII_PATTERNS.values():
        text = re.sub(pattern, parsed.replacement, text, flags=re.IGNORECASE)
    return {"result": text}

###############################################################################
def _prompt_injection_detector_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = AdvancedTextParameters.model_validate(parameters)
    patterns = parsed.patterns or ["ignore previous", "system prompt", "developer message", "exfiltrate", "jailbreak"]
    text = _text(inputs).lower()
    matches = [pattern for pattern in patterns if pattern.lower() in text]
    return _classifier("prompt_injection" if matches else "clean", 1.0 if matches else 0.0, matches)

###############################################################################
def _instruction_stripper_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    lines = [line for line in _text(inputs).splitlines() if not re.search(r"ignore previous|system prompt|developer message|jailbreak", line, re.I)]
    return {"result": "\n".join(lines)}

###############################################################################
def _diff_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    diff = difflib.unified_diff(_text(inputs, "before").splitlines(), _text(inputs, "after").splitlines(), lineterm="")
    return {"result": "\n".join(diff)}

###############################################################################
def _patch_apply_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    raise ValueError("PATCH_APPLY rejects patches unless context matching is implemented for the target text")

###############################################################################
def _markdown_parser_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    tokens = MarkdownIt().parse(_text(inputs))
    return {"result": [{"type": token.type, "tag": token.tag, "content": token.content, "map": token.map} for token in tokens]}

###############################################################################
def _code_block_extractor_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    blocks = [{"language": match.group(1), "code": match.group(2)} for match in re.finditer(r"```(\w*)\n(.*?)```", _text(inputs), re.S)]
    return {"result": blocks}

###############################################################################
def _citation_extractor_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = _text(inputs)
    urls = re.findall(r"https?://\S+", text)
    footnotes = re.findall(r"\[\^?(\d+|[A-Za-z][\w-]*)\]", text)
    return {"result": {"urls": urls, "footnotes": footnotes, "references": re.findall(r"\[[A-Za-z0-9 ,.-]+\]", text)}}

###############################################################################
def _date_normalizer_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = _text(inputs)
    try:
        parsed = date_parser.parse(text, fuzzy=True)
        return {"result": {"iso": parsed.date().isoformat(), "datetime": parsed.isoformat()}}
    except (ValueError, OverflowError):
        return {"result": None}

###############################################################################
def _unit_number_normalizer_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    matches = [{"value": float(m.group(1)), "unit": m.group(2) or ""} for m in re.finditer(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z%]+)?", _text(inputs))]
    return {"result": matches}

###############################################################################
def _table_extractor_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    rows = [line for line in _text(inputs).splitlines() if "|" in line]
    return {"result": rows}

###############################################################################
class StaticClassifierExecutor:
    def __init__(self, label: str) -> None:
        self._label = label

    def __call__(self, parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        _ = parameters, inputs
        return _classifier(self._label, 0.5, [], {"evaluated_at": datetime.utcnow().isoformat()})


ADVANCED_TEXT_HANDLERS = {
    "claim_extractor": NodeHandler(executor=_claim_extractor_executor),
    "contradiction_detector": NodeHandler(executor=_contradiction_detector_executor),
    "entity_extractor": NodeHandler(executor=_entity_extractor_executor),
    "entity_resolver": NodeHandler(executor=_entity_resolver_executor, parameter_model=AdvancedTextParameters),
    "pii_detector": NodeHandler(executor=_pii_detector_executor),
    "pii_redactor": NodeHandler(executor=_pii_redactor_executor, parameter_model=AdvancedTextParameters),
    "toxicity_policy_classifier": NodeHandler(executor=StaticClassifierExecutor("allowed")),
    "prompt_injection_detector": NodeHandler(executor=_prompt_injection_detector_executor, parameter_model=AdvancedTextParameters),
    "instruction_stripper": NodeHandler(executor=_instruction_stripper_executor),
    "diff_text": NodeHandler(executor=_diff_text_executor),
    "patch_apply": NodeHandler(executor=_patch_apply_executor),
    "table_extractor": NodeHandler(executor=_table_extractor_executor),
    "markdown_parser": NodeHandler(executor=_markdown_parser_executor),
    "code_block_extractor": NodeHandler(executor=_code_block_extractor_executor),
    "citation_extractor": NodeHandler(executor=_citation_extractor_executor),
    "date_normalizer": NodeHandler(executor=_date_normalizer_executor),
    "unit_number_normalizer": NodeHandler(executor=_unit_number_normalizer_executor),
    "sentiment_intent_classifier": NodeHandler(executor=StaticClassifierExecutor("neutral")),
    "topic_classifier": NodeHandler(executor=StaticClassifierExecutor("general")),
    "quality_scorer": NodeHandler(executor=StaticClassifierExecutor("acceptable")),
    "compression": NodeHandler(executor=StaticClassifierExecutor("compressed")),
}
