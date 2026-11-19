"""
tests/conftest.py
~~~~~~~~~~~~~~~~~
Global pytest configuration and fixtures for Railway Traffic Optimizer test suite.
"""

from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def isolate_railway_runtime_dir(tmp_path, monkeypatch):
    """Isolate runtime state directory to tmp_path to prevent mutating repository state during test runs."""
    monkeypatch.setenv("RAILWAY_RUNTIME_DIR", str(tmp_path))
    # Import backend first to avoid circular import between state_manager and backend.app.main
    import backend.app.main
    import simulation.state_manager as sm
    sm._sim_manager_cache = None
    yield
    sm._sim_manager_cache = None
