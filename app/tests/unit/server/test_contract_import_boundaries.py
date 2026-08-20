from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_IMPORT_PREFIXES = (
    "fastapi",
    "server.api",
    "server.repositories",
    "server.services",
    "sqlalchemy",
)


def test_contract_modules_remain_transport_and_persistence_neutral() -> None:
    contract_root = Path(__file__).resolve().parents[3] / "server" / "contracts"

    for path in sorted(contract_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported_modules = [node.module or ""]
            else:
                continue

            for module in imported_modules:
                assert not any(
                    module == prefix or module.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_IMPORT_PREFIXES
                ), f"{path} imports forbidden runtime module {module}"
