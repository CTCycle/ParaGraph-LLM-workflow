from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


###############################################################################
def test_generated_frontend_api_contracts_match_fastapi_openapi() -> None:
    root = Path(__file__).resolve().parents[4]
    generator = root / "app/scripts/generate_frontend_api_contracts.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "app")

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
