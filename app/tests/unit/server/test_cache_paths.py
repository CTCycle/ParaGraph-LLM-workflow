from __future__ import annotations

import os
import sys
from pathlib import Path

from server.common import path as common_path


def test_application_cache_root_is_repository_canonical() -> None:
    expected_root = Path(__file__).resolve().parents[4] / "runtimes" / "cache"

    assert common_path.CACHE_ROOT == expected_root
    assert common_path.FRONTEND_DIST_ROOT == expected_root / "frontend-dist"
    assert sys.pycache_prefix == str(expected_root / "pycache")


def test_library_cache_environment_is_repository_canonical() -> None:
    expected_root = common_path.CACHE_ROOT

    assert os.environ["PYTHONPYCACHEPREFIX"] == str(expected_root / "pycache")
    assert os.environ["HF_HOME"] == str(expected_root / "huggingface")
    assert os.environ["HF_HUB_CACHE"] == str(expected_root / "huggingface" / "hub")
    assert os.environ["HF_ASSETS_CACHE"] == str(
        expected_root / "huggingface" / "assets"
    )
    assert os.environ["HF_XET_CACHE"] == str(expected_root / "huggingface" / "xet")
    assert os.environ["TORCH_HOME"] == str(expected_root / "torch")
