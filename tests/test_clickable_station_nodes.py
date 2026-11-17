"""
tests/test_clickable_station_nodes.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Focused test suite for Requirement #11:
1. Audit Division Topology station nodes and ensure EVERY station is clickable.
2. Verify authoritative data flow on station selection:
   - station identity/name
   - corridor
   - station type/category
   - connected routes/track sections
   - platforms
   - junction/interlocking information where applicable
   - services/trains associated with the station
   - timetable information
   - current simulation/operational state when available
"""

from __future__ import annotations

import json
import os
import re
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    NetworkResponse,
    SimulateResponse,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Authoritative Backend Infrastructure Contracts for Topology
# ---------------------------------------------------------------------------

def test_network_topology_api_authoritative_data():
    """Verify /api/v1/network returns complete authoritative topology with platforms and track sections."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    data = resp.json()

    network = NetworkResponse(**data)
    assert network.station_count == 30
    assert network.junction_count == 7
    assert network.route_count >= 10
    assert network.service_count == 47
    assert network.track_section_count >= 100

    # Verify platforms array
    assert network.platforms is not None
    assert len(network.platforms) == 14
    for p in network.platforms:
        assert p.station_id in ("MAS", "BBQ", "MSB", "MS", "TBM", "CGL", "AJJ")
        assert p.platform_number >= 1
        assert p.capacity >= 12

    # Verify track sections array
    assert network.track_sections is not None
    assert len(network.track_sections) >= 300
    sample_section = network.track_sections[0]
    assert sample_section.id is not None
    assert sample_section.from_node is not None
    assert sample_section.to_node is not None
    assert sample_section.travel_time_minutes > 0

    # Verify junctions
    jct_ids = {j.id for j in network.junctions}
    assert "JCT_BBQ" in jct_ids
    assert "JCT_VJM" in jct_ids
    assert "JCT_KOK" in jct_ids
    assert "JCT_MSB" in jct_ids
    assert "JCT_CGL" in jct_ids
    assert "JCT_AJJ" in jct_ids
    assert "JCT_PAB" in jct_ids

    # Verify junctions have descriptions and connected routes
    for j in network.junctions:
        assert j.junction_type in ("CRITICAL_THROAT", "CORRIDOR_DIVERGENCE", "CORRIDOR_MERGE", "MULTI_CORRIDOR_HUB", "BRANCH")
        assert len(j.connected_routes) > 0


# ---------------------------------------------------------------------------
# 2. Complete Station Node Coverage and Clickability in NetworkTopologyView
# ---------------------------------------------------------------------------

def test_all_107_stations_defined_and_clickable_in_ui():
    """Verify NetworkTopologyView.tsx maps all 107 nodes and provides click handlers for every station."""
    path = os.path.join("frontend", "src", "components", "NetworkTopologyView.tsx")
    assert os.path.exists(path), f"File {path} not found"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract all node IDs defined in NODES
    node_matches = re.findall(r'id:\s*"([A-Za-z0-9_]+)",\s*name:', content)
    assert len(node_matches) == 107, f"Expected 107 stations in NODES array, found {len(node_matches)}"

    # Check that major hubs are all present
    must_have_nodes = ["MAS", "BBQ", "VJM", "PER", "AVD", "TRL", "AJJ", "KOK", "TVT", "ENR", "GPD", "SPE", "MSB", "MS", "TBM", "CGL", "CJ", "VLCY", "PTMS"]
    for node_id in must_have_nodes:
        assert node_id in node_matches, f"Node {node_id} must be in NODES array"

    # Verify that every node has an onClick handler and data-testid
    assert 'data-testid={`station-node-${node.id}`}' in content
    assert 'onClick={() => setSelectedNode(isSel ? null : node.id)}' in content
    assert 'cursor: "pointer"' in content

    # Verify that an enlarged transparent hit area exists so clicking is effortless
    assert 'fill="transparent"' in content

    # Verify presence of Station Selector dropdown in the toolbar
    assert 'data-testid="station-selector-dropdown"' in content
    assert 'Jump to Station...' in content


# ---------------------------------------------------------------------------
# 3. Authoritative Station Data Flow Contracts on Click
# ---------------------------------------------------------------------------

def test_station_click_data_flow_contracts():
    """Verify NetworkTopologyView.tsx implements all required sections in the Inspector panel."""
    path = os.path.join("frontend", "src", "components", "NetworkTopologyView.tsx")
    assert os.path.exists(path), f"File {path} not found"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Inspector panel container
    assert 'data-testid="station-inspector-panel"' in content

    # 2. Station Identity & Name & Corridor
    assert 'selNode.id' in content
    assert 'selNode.name' in content
    assert 'Chennai Division (MAS) • Southern Railway' in content
    assert 'stationCategory' in content
    assert 'CORRIDOR_FULL_NAMES' in content

    # 3. Platforms Information
    assert 'Platforms (' in content
    assert 'stationPlatforms' in content
    assert 'platformCount' in content

    # 4. Junction & Interlocking Information
    assert 'Junction & Interlocking' in content
    assert 'selJunction.junction_type' in content
    assert 'selJunction.capacity' in content
    assert 'selJunction.description' in content
    assert 'selJunction.connected_routes' in content
    assert 'Interlocking Classification' in content

    # 5. Connected Routes & Track Sections
    assert 'Connected Routes (' in content
    assert 'connectedRoutes' in content
    assert 'Track Sections (' in content
    assert 'connectedSections' in content
    assert 'Adjacent Stations' in content

    # 6. Services & Timetable Information
    assert 'Associated Services (' in content
    assert 'associatedServices' in content
    assert 'Station Timetable (' in content
    assert 'stationTimetable' in content

    # 7. Current Simulation & Operational State
    assert 'Active Trains at Station (' in content
    assert 'liveTrainsAtStation' in content
    assert 'Active Station Conflicts (' in content
    assert 'activeConflictsAtStation' in content
    assert 'delay_minutes' in content

    # 8. Empty state when no station is clicked
    assert 'data-testid="inspector-empty-state"' in content
    assert 'Division Station Inspector' in content


# ---------------------------------------------------------------------------
# 4. End-to-End Topology Data Resolution for Different Station Types
# ---------------------------------------------------------------------------

def test_topology_data_resolution_for_station_types():
    """Verify data resolution for a Terminal (MAS), a Junction (BBQ), and an Intermediate Station (PER)."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    data = resp.json()
    net = NetworkResponse(**data)

    # 1. Terminal Station: MAS
    mas_stn = next(s for s in net.stations if s.id == "MAS")
    assert mas_stn.station_type == "Terminal"
    assert mas_stn.platform_count == 15
    mas_platforms = [p for p in net.platforms if p.station_id == "MAS"]
    assert len(mas_platforms) == 2  # MAS_P1, MAS_P2 modeled
    mas_routes = [r for r in net.routes if "MAS" in r.ordered_nodes]
    assert len(mas_routes) >= 4
    mas_sections = [ts for ts in net.track_sections if ts.from_node == "MAS" or ts.to_node == "MAS"]
    assert len(mas_sections) == 2  # MAS-BBQ Up and Down mainline throat tracks
    mas_tt = [tt for tt in net.timetable if tt["station_id"] == "MAS"]
    assert len(mas_tt) >= 15

    # 2. Junction Station: BBQ
    bbq_stn = next(s for s in net.stations if s.id == "BBQ")
    assert bbq_stn.station_type == "Junction Station"
    bbq_jct = next(j for j in net.junctions if j.station_id == "BBQ")
    assert bbq_jct.junction_type == "CRITICAL_THROAT"
    assert bbq_jct.capacity == 1
    assert len(bbq_jct.connected_routes) >= 4
    bbq_sections = [ts for ts in net.track_sections if ts.from_node == "BBQ" or ts.to_node == "BBQ"]
    assert len(bbq_sections) >= 6

    # 3. Regular Intermediate Station: PER (Perambur)
    per_stn = next(s for s in net.stations if s.id == "PER")
    assert per_stn.station_type == "Regular"
    assert per_stn.platform_count == 4
    per_routes = [r for r in net.routes if "PER" in r.ordered_nodes]
    assert len(per_routes) >= 2
    per_sections = [ts for ts in net.track_sections if ts.from_node == "PER" or ts.to_node == "PER"]
    assert len(per_sections) >= 2
