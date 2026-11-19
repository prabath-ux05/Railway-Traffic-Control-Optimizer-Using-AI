"""Tests for Batch 3: Data Integrity, Active Services, Route Node Registry, and Provenance.

Validates:
1. Active and excluded services (40 active, 7 excluded with 'No published timetable evidence').
2. Rejection of explicit requests for excluded services with HTTP 400.
3. Health endpoint integrity reporting (836 warnings, categorized summary, WARNINGS status, datasets_intact preserved).
4. Route node registry in /network (107 unique route nodes, platform counts, corridor mappings, PAB as junction).
5. Provenance reporting in /network (erail.in 103, railyatri.in 22, confirmtkt.com 2, PUBLIC_REFERENCE 127, snapshot date, dataset hashes).
6. Station registry proposal file (data/proposals/stations_extended.json) with 77 entries, verification status, and stations.json untouched.
7. Platform conflicts feature flag (OFF by default = 0 assignments, ON = assigns available platforms).
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api import get_network
from optimization.model import OptimizationRequest
from optimization.solver import CPSATScheduler


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def network():
    return get_network()


# =========================================================================
# 3.1 ACTIVE AND EXCLUDED SERVICES
# =========================================================================

EXPECTED_EXCLUDED_SERVICE_IDS = {
    "SRV_40143_01",
    "SRV_40144_01",
    "SRV_41015_01",
    "SRV_41131_01",
    "SRV_41132_01",
    "SRV_42413_01",
    "SRV_42425_01",
}


def test_active_and_excluded_service_counts(network):
    """Network must derive 40 active services and exactly 7 excluded services."""
    assert len(network.services) == 47
    assert len(network.active_services) == 40
    assert len(network.excluded_services) == 7

    assert set(network.excluded_services.keys()) == EXPECTED_EXCLUDED_SERVICE_IDS

    for s_id, svc in network.active_services.items():
        assert svc.active is True
        assert svc.exclusion_reason is None

    for s_id, svc in network.excluded_services.items():
        assert svc.active is False
        assert svc.exclusion_reason == "No published timetable evidence"


def test_network_endpoint_service_metadata(client):
    """GET /network must expose active and exclusion_reason per service plus active/excluded counts."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    data = resp.json()

    assert data["service_count"] == 47
    assert data["active_service_count"] == 40
    assert data["excluded_service_count"] == 7

    services = data["services"]
    assert len(services) == 47

    excluded_svcs = [s for s in services if not s["active"]]
    assert len(excluded_svcs) == 7
    for s in excluded_svcs:
        assert s["id"] in EXPECTED_EXCLUDED_SERVICE_IDS
        assert s["exclusion_reason"] == "No published timetable evidence"


def test_explicit_request_for_excluded_service_rejected(client):
    """Explicit request for an excluded service must return HTTP 400 with a clear message."""
    excluded_id = "SRV_40143_01"

    # 1. /simulate
    r1 = client.post("/api/v1/simulate", json={"service_ids": [excluded_id]})
    assert r1.status_code == 400
    assert f"Service '{excluded_id}' is excluded" in r1.json()["detail"]
    assert "No published timetable evidence" in r1.json()["detail"]

    # 2. /optimize
    r2 = client.post("/api/v1/optimize", json={"service_ids": [excluded_id]})
    assert r2.status_code == 400
    assert f"Service '{excluded_id}' is excluded" in r2.json()["detail"]
    assert "No published timetable evidence" in r2.json()["detail"]

    # 3. /what-if
    r3 = client.post("/api/v1/what-if", json={"service_ids": [excluded_id]})
    assert r3.status_code == 400
    assert f"Service '{excluded_id}' is excluded" in r3.json()["detail"]
    assert "No published timetable evidence" in r3.json()["detail"]

    # 4. /simulation/control
    r4 = client.post("/api/v1/simulation/control", json={"service_ids": [excluded_id]})
    assert r4.status_code == 400
    assert f"Service '{excluded_id}' is excluded" in r4.json()["detail"]


# =========================================================================
# 3.2 HEALTH INTEGRITY
# =========================================================================

def test_health_integrity_warnings_and_status(client):
    """GET /health must retain datasets_intact and report integrity warning count and breakdown."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()

    # datasets_intact must remain unchanged
    net_status = data["network_status"]
    assert net_status["datasets_intact"] is True

    # 836 integrity warnings
    assert data["integrity_warning_count"] == 836
    assert net_status["integrity_warning_count"] == 836
    assert data["datasets_integrity_status"] == "WARNINGS"
    assert net_status["datasets_integrity_status"] == "WARNINGS"

    # Categorized integrity summary
    summary = data["integrity_summary"]
    assert summary["station_record_missing_for_route_node"] == 749
    assert summary["no_track_section_for_hop"] == 83
    assert summary["timetable_references_unknown_station"] == 4
    assert sum(summary.values()) == 836


# =========================================================================
# 3.3 ROUTE NODE REGISTRY
# =========================================================================

def test_route_node_registry_in_network(client):
    """GET /network must return 107 route nodes with proper classifications and platform counts."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    data = resp.json()

    nodes = data.get("nodes", [])
    assert len(nodes) == 107

    nodes_by_id = {n["id"]: n for n in nodes}

    # Exactly 30 have station records; 77 do not
    stations_with_records = [n for n in nodes if n["has_station_record"]]
    assert len(stations_with_records) == 30

    # PAB is a junction without station record
    assert "PAB" in nodes_by_id
    pab = nodes_by_id["PAB"]
    assert pab["has_station_record"] is False
    assert pab["node_type"] == "JUNCTION"
    assert pab["name"] == "Pattabiram Junction"
    assert "West" in pab["corridors"] or "PTMS" in pab["corridors"]

    # Platform counts: MAS, BBQ, MSB, MS, TBM, CGL, AJJ have 2 platforms
    for stn_id in ["MAS", "BBQ", "MSB", "MS", "TBM", "CGL", "AJJ"]:
        assert nodes_by_id[stn_id]["platform_count"] == 2

    # Regular waypoint without station record has null name
    assert "EGT" in nodes_by_id
    egt = nodes_by_id["EGT"]
    assert egt["has_station_record"] is False
    assert egt["name"] is None
    assert egt["node_type"] == "WAYPOINT"


# =========================================================================
# 3.4 PROVENANCE
# =========================================================================

def test_data_provenance_in_network(client):
    """GET /network must expose timetable source breakdown, dataset hashes, and snapshot date."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    data = resp.json()

    prov = data.get("data_provenance")
    assert prov is not None

    assert prov["snapshot_date"] == "2026-09-26"

    # Expected: erail.in 103, railyatri.in 22, confirmtkt.com 2
    sources = prov["timetable_sources"]
    assert sources.get("erail.in") == 103
    assert sources.get("railyatri.in") == 22
    assert sources.get("confirmtkt.com") == 2
    assert sum(sources.values()) == 127

    # data_source: PUBLIC_REFERENCE for all 127
    assert prov["timetable_data_sources"].get("PUBLIC_REFERENCE") == 127

    # File hashes for all master datasets
    hashes = prov["dataset_sha256_hashes"]
    assert len(hashes) == 13
    assert "infrastructure/stations.json" in hashes
    assert "trains/published_timetables/timetable.json" in hashes


# =========================================================================
# 3.5 STATION REGISTRY PROPOSAL
# =========================================================================

def test_station_registry_proposal_file():
    """Verify data/proposals/stations_extended.json covers all 77 nodes and stations.json is unchanged."""
    proposal_path = os.path.join("data", "proposals", "stations_extended.json")
    assert os.path.isfile(proposal_path)

    with open(proposal_path, "r", encoding="utf-8") as f:
        proposals = json.load(f)

    assert len(proposals) == 77
    prop_by_id = {p["id"]: p for p in proposals}

    # Verify required fields
    for p in proposals:
        assert "id" in p
        assert "name" in p
        assert "source_url" in p
        assert "accessed_on" in p
        assert "verification_status" in p
        assert p["verification_status"] in ("VERIFIED", "UNVERIFIED")

    # 7 requested nodes must be UNVERIFIED
    for unverified_id in ["PLMG", "MSU", "TO", "MAF", "SPAM", "KBT", "EGT"]:
        assert unverified_id in prop_by_id
        assert prop_by_id[unverified_id]["verification_status"] == "UNVERIFIED"

    # PAB is verified junction
    assert prop_by_id["PAB"]["verification_status"] == "VERIFIED"
    assert prop_by_id["PAB"]["name"] == "Pattabiram Junction"

    # stations.json must remain strictly unmodified with 30 stations
    with open(os.path.join("data", "infrastructure", "stations.json"), "r", encoding="utf-8") as f:
        stations = json.load(f)
    assert len(stations) == 30
    assert "PAB" not in {s["id"] for s in stations}


# =========================================================================
# 3.6 PLATFORM CONFLICTS (FEATURE FLAG)
# =========================================================================

def test_platform_conflicts_feature_flag(network):
    """Platform allocations must be empty by default and populated when flag is enabled."""
    solver = CPSATScheduler(time_limit_seconds=5.0)

    # 1. Flag OFF (default): platform allocations empty
    req_off = OptimizationRequest.from_network_and_state(network, service_ids=["SRV_12607_01"])
    res_off = solver.schedule(req_off)
    pf_off = [d for d in res_off.resource_decisions if d.resource_type == "PLATFORM"]
    assert len(pf_off) == 0

    # 2. Flag ON: platform allocations populated for stations with platforms
    req_on = OptimizationRequest.from_network_and_state(network, service_ids=["SRV_12607_01"])
    req_on.enable_platform_conflicts = True
    res_on = solver.schedule(req_on)
    pf_on = [d for d in res_on.resource_decisions if d.resource_type == "PLATFORM"]
    assert len(pf_on) > 0
    assigned_stations = {d.node_or_section_id for d in pf_on}
    assert "MAS" in assigned_stations
    assert "AJJ" in assigned_stations
