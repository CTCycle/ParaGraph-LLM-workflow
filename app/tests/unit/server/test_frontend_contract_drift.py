from __future__ import annotations

import re
from pathlib import Path


###############################################################################
def _literal_members(source: str, declaration: str) -> set[str]:
    match = re.search(
        rf"{re.escape(declaration)}\s*=\s*(?:Literal\[)?(?P<body>.*?)(?:\]|\nexport interface)",
        source,
        re.DOTALL,
    )
    assert match, f"Could not find {declaration}"
    return set(re.findall(r"['\"]([A-Z][A-Z0-9_]*)['\"]", match.group("body")))


###############################################################################
def test_frontend_node_data_types_match_backend_contract() -> None:
    root = Path(__file__).resolve().parents[4]
    backend = (root / "app/server/contracts/node_catalog.py").read_text(
        encoding="utf-8"
    )
    frontend = (root / "app/client/src/workflow/schema/types.ts").read_text(
        encoding="utf-8"
    )

    backend_types = _literal_members(backend, "NodeDataType")
    frontend_types = _literal_members(frontend, "export type NodeDataType")
    assert frontend_types == backend_types
