import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import mcp_tools


@pytest.fixture(autouse=True)
def _reset_module_caches():
    mcp_tools._reset_diffopt_patch_cache()
    yield
    mcp_tools._reset_diffopt_patch_cache()
