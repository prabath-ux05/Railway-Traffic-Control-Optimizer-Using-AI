"""
tests/test_delay_meter_scale.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Focused test suite for Requirement #9:
Delay Meter Scale Update from 5-minute increments (0, 5, 10, ... 60)
to 1-minute increments (0, 1, 2, 3, ... 60).

Verifies:
1. OptimizationPanel.tsx:
   - Departure delay range slider has min="0", max="60", step="1"
   - Station dwell delay input has min="0", max="60", step="1"
2. SimulationMonitor.tsx:
   - Delay magnitude slider has min="0", max="60", step="1"
3. WhatIfStudio.tsx:
   - Departure delay input has min="0", max="60", step="1"
   - En-route dwell delay input has min="0", max="60", step="1"
4. Verification of absence of obsolete step="5" on delay meter controls
5. Backend validation that single-minute delays (e.g. 1m, 2m, 3m) are accepted
   and correctly processed by optimization and simulation pipelines.
"""

from __future__ import annotations

import os
import re
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_optimization_panel_delay_scale():
    """Verify OptimizationPanel.tsx has 1-minute step scale (0 to 60) for delay inputs."""
    path = os.path.join("frontend", "src", "components", "OptimizationPanel.tsx")
    assert os.path.exists(path), f"File {path} not found"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Injected departure delay slider
    slider_match = re.search(
        r'<input[^>]*type="range"[^>]*min="0"[^>]*max="60"[^>]*step="1"[^>]*value=\{injectedDelayMinutes\}',
        content,
    )
    assert slider_match is not None, "OptimizationPanel delay range slider must have min='0' max='60' step='1'"

    # Station dwell delay input
    dwell_match = re.search(
        r'<input[^>]*type="number"[^>]*min="0"[^>]*max="60"[^>]*step="1"[^>]*placeholder="Min"[^>]*value=\{stationDwellDelay',
        content,
    )
    assert dwell_match is not None, "OptimizationPanel station dwell delay input must have min='0' max='60' step='1'"


def test_simulation_monitor_delay_scale():
    """Verify SimulationMonitor.tsx has 1-minute step scale (0 to 60) for delay magnitude slider."""
    path = os.path.join("frontend", "src", "components", "SimulationMonitor.tsx")
    assert os.path.exists(path), f"File {path} not found"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Delay magnitude range slider
    slider_match = re.search(
        r'<input[^>]*type="range"[^>]*min="0"[^>]*max="60"[^>]*step="1"[^>]*value=\{delayInputMinutes\}',
        content,
    )
    assert slider_match is not None, "SimulationMonitor delay magnitude slider must have min='0' max='60' step='1'"

    # Confirm obsolete min="5" and step="5" are not present for delayInputMinutes
    assert 'min="5"' not in content, "Obsolete min='5' should be replaced by min='0'"


def test_what_if_studio_delay_scale():
    """Verify WhatIfStudio.tsx has 1-minute step scale (0 to 60) for departure and dwell delay inputs."""
    path = os.path.join("frontend", "src", "components", "WhatIfStudio.tsx")
    assert os.path.exists(path), f"File {path} not found"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Departure delay input
    dep_match = re.search(
        r'<input[^>]*type="number"[^>]*min="0"[^>]*max="60"[^>]*step="1"[^>]*value=\{depDelayInput',
        content,
    )
    assert dep_match is not None, "WhatIfStudio departure delay input must have min='0' max='60' step='1'"

    # En-route dwell delay input
    dwell_match = re.search(
        r'<input[^>]*type="number"[^>]*min="0"[^>]*max="60"[^>]*step="1"[^>]*placeholder="Min"[^>]*value=\{stnDwellInput',
        content,
    )
    assert dwell_match is not None, "WhatIfStudio en-route dwell delay input must have min='0' max='60' step='1'"


def test_no_obsolete_step_5_on_delay_meters():
    """Ensure no delay control in the entire frontend still uses step='5'."""
    frontend_components = [
        os.path.join("frontend", "src", "components", "OptimizationPanel.tsx"),
        os.path.join("frontend", "src", "components", "SimulationMonitor.tsx"),
        os.path.join("frontend", "src", "components", "WhatIfStudio.tsx"),
    ]

    for comp_path in frontend_components:
        with open(comp_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            if 'step="5"' in line:
                # Should not be present on any delay control
                assert False, f"Found obsolete step='5' at {comp_path}:{idx}: {line.strip()}"


def test_api_accepts_fine_grained_single_minute_delays():
    """Verify backend optimization and what-if endpoints accept 1-minute granular delays (e.g. 1m, 2m, 3m)."""
    # 1. Test What-If with a 1-minute delay and 3-minute delay
    payload = {
        "scenario_id": "SCEN_REQ9_TEST",
        "scenario_name": "Requirement 9 Fine-Grained Delay Scale Test",
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {
            "SRV_12607_01": 1.0,
            "SRV_12609_01": 3.0,
        },
        "station_delays": {
            "SRV_12607_01": {"PER": 2.0}
        },
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200, f"What-If endpoint failed: {response.text}"
    data = response.json()
    assert data["scenario_id"] == "SCEN_REQ9_TEST"
    assert data["baseline_comparison"]["feasible_baseline_delay_minutes"] > 0

    # 2. Test Optimize with 1-minute delay
    opt_payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {
            "SRV_12607_01": 1.0,
        },
    }
    opt_response = client.post("/api/v1/optimize", json=opt_payload)
    assert opt_response.status_code == 200, f"Optimize endpoint failed: {opt_response.text}"
    opt_data = opt_response.json()
    assert opt_data["solver_status"] in ["OPTIMAL", "FEASIBLE"]
