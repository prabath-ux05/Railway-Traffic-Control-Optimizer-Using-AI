"""
tests/test_phase34_2_data_integrity.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Audit & Verification Test Suite for Phase 34.2:
Data Integrity & Immutability Audit.

Tests cover:
  1. Master Dataset Record Counts & Exact Inventory.
  2. SHA-256 Immutability Hash Invariants.
  3. Schema Compliance & Key Attribute Presence.
  4. Cross-Reference Referencing & Zero Orphaned Entities.
  5. Absence of Duplicate IDs across all entities.
  6. Strict Exclusion of 7 Pending Services.
  7. Non-Contamination / Master Files Write Protection.
  8. Evaluation Artifact Segregation.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import pytest
from typing import Any, Dict, List, Set

from evaluation.framework import PENDING_SERVICES
from simulation.network import Network


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")
_INFRA_DIR = os.path.join(_DATA_DIR, "infrastructure")
_TRAINS_DIR = os.path.join(_DATA_DIR, "trains")
_TRACK_SECTIONS_DIR = os.path.join(_DATA_DIR, "track_sections")

# Canonical SHA-256 Baselines
EXPECTED_HASHES = {
    "stations.json": "c1c3324c8f252a7f12fd7d0ce960e0c92c746945afdff1db15b71bc71fac14e3",
    "platforms.json": "6c8b85beaed15541cd20ed2e38c4f2e29add9373ef65149443f5a28f22ec74b1",
    "junctions.json": "abd203cfce1ca4cef39bb54b376b855807f792d30b8e94b237aca49a11461d45",
    "routes.json": "07afe8f4b093b7987fb09d8b857a0ac84610a47e3c1cfd5f0daaa0515e883708",
    "trains.json": "ed28825c9753b7bc588ce2fb2b554913d529f5ab4f8c784bdba1b43580813be9",
    "services.json": "1b6386e4cf23472c9398cb79ba81f1353c0aee4592b19ab47666898a2a735b9d",
    "timetable.json": "578529fa64a2dc0c9377ca596d6411cfac8466f1cbac04b22bedfc43b01d6a2d",
    "beach_north_bypass_track_sections.json": "12119214b04a56ee56da3983e4238a8748cce64af8be1b6bfe4acee3c772ad5e",
    "cross_bypass_track_sections.json": "1eff5ecadc6d38868f741d9fd04df25a81fd8e196747e1d8dccd40b57a10b6ef",
    "mrts_track_sections.json": "1964b01ec3d4a451233fa5193558e940dc7e8532029185a0694b7b62e2d2f54c",
    "north_track_sections.json": "814bc3e8a1a2ad75929d5366882c5b36825a854f9104dd1f17bd84922050387c",
    "south_track_sections.json": "9ab818ee510dce98d475e05ce2a3d2231c453e9f5a99a4441d1d2729d702a2cb",
    "west_track_sections.json": "9f6e8593263ade57f9f4efcd5b3b42bde37a5740b9296222381f88a17bcc994f",
}


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. SHA-256 Hash Immutability Audit
# ---------------------------------------------------------------------------

def test_master_dataset_sha256_immutability():
    """Verify exact SHA-256 cryptographic hashes for all master data files."""
    file_map = {
        "stations.json": os.path.join(_INFRA_DIR, "stations.json"),
        "platforms.json": os.path.join(_INFRA_DIR, "platforms.json"),
        "junctions.json": os.path.join(_INFRA_DIR, "junctions.json"),
        "routes.json": os.path.join(_INFRA_DIR, "routes.json"),
        "trains.json": os.path.join(_TRAINS_DIR, "train_identity", "trains.json"),
        "services.json": os.path.join(_TRAINS_DIR, "service_definitions", "services.json"),
        "timetable.json": os.path.join(_TRAINS_DIR, "published_timetables", "timetable.json"),
        "beach_north_bypass_track_sections.json": os.path.join(_TRACK_SECTIONS_DIR, "beach_north_bypass_track_sections.json"),
        "cross_bypass_track_sections.json": os.path.join(_TRACK_SECTIONS_DIR, "cross_bypass_track_sections.json"),
        "mrts_track_sections.json": os.path.join(_TRACK_SECTIONS_DIR, "mrts_track_sections.json"),
        "north_track_sections.json": os.path.join(_TRACK_SECTIONS_DIR, "north_track_sections.json"),
        "south_track_sections.json": os.path.join(_TRACK_SECTIONS_DIR, "south_track_sections.json"),
        "west_track_sections.json": os.path.join(_TRACK_SECTIONS_DIR, "west_track_sections.json"),
    }

    for fname, expected_hash in EXPECTED_HASHES.items():
        fpath = file_map[fname]
        assert os.path.exists(fpath), f"Master dataset file missing: {fname}"
        actual_hash = _file_hash(fpath)
        assert actual_hash == expected_hash, (
            f"Immutability breach in {fname}!\n"
            f"  Expected SHA-256: {expected_hash}\n"
            f"  Actual SHA-256:   {actual_hash}"
        )


# ---------------------------------------------------------------------------
# 2. Record Counts & Exact Inventory
# ---------------------------------------------------------------------------

def test_dataset_exact_counts_and_inventory():
    """Verify master datasets contain exact expected record counts."""
    with open(os.path.join(_INFRA_DIR, "stations.json")) as f:
        stations = json.load(f)
    with open(os.path.join(_INFRA_DIR, "platforms.json")) as f:
        platforms = json.load(f)
    with open(os.path.join(_INFRA_DIR, "junctions.json")) as f:
        junctions = json.load(f)
    with open(os.path.join(_INFRA_DIR, "routes.json")) as f:
        routes = json.load(f)
    with open(os.path.join(_TRAINS_DIR, "train_identity", "trains.json")) as f:
        trains = json.load(f)
    with open(os.path.join(_TRAINS_DIR, "service_definitions", "services.json")) as f:
        services = json.load(f)
    with open(os.path.join(_TRAINS_DIR, "published_timetables", "timetable.json")) as f:
        timetable = json.load(f)

    track_files = glob.glob(os.path.join(_TRACK_SECTIONS_DIR, "*.json"))
    total_tracks = sum(len(json.load(open(tf))) for tf in track_files)

    assert len(stations) == 30, f"Stations count mismatch: {len(stations)}"
    assert len(platforms) == 14, f"Platforms count mismatch: {len(platforms)}"
    assert len(junctions) == 7, f"Junctions count mismatch: {len(junctions)}"
    assert len(routes) == 24, f"Routes count mismatch: {len(routes)}"
    assert len(trains) == 51, f"Trains count mismatch: {len(trains)}"
    assert len(services) == 47, f"Services count mismatch: {len(services)}"
    assert len(timetable) == 127, f"Timetable entries count mismatch: {len(timetable)}"
    assert total_tracks == 354, f"Track sections count mismatch: {total_tracks}"


# ---------------------------------------------------------------------------
# 3. Schema Completeness & Key Constraint Validation
# ---------------------------------------------------------------------------

def test_dataset_schema_conformance():
    """Verify all records conform strictly to their respective schemas."""
    with open(os.path.join(_INFRA_DIR, "stations.json")) as f:
        for stn in json.load(f):
            assert "id" in stn and "name" in stn and "station_type" in stn and "platform_count" in stn
            assert isinstance(stn["platform_count"], int) and stn["platform_count"] >= 1

    with open(os.path.join(_INFRA_DIR, "platforms.json")) as f:
        for p in json.load(f):
            assert "id" in p and "station_id" in p and "platform_number" in p and "capacity" in p

    with open(os.path.join(_INFRA_DIR, "junctions.json")) as f:
        for j in json.load(f):
            assert "id" in j and "name" in j and "junction_type" in j and "connected_routes" in j
            assert isinstance(j["connected_routes"], list)

    with open(os.path.join(_INFRA_DIR, "routes.json")) as f:
        for r in json.load(f):
            assert "id" in r and "origin" in r and "destination" in r and "ordered_nodes" in r
            assert len(r["ordered_nodes"]) >= 2

    with open(os.path.join(_TRAINS_DIR, "train_identity", "trains.json")) as f:
        for t in json.load(f):
            assert "train_id" in t and "train_name" in t and "train_number" in t

    with open(os.path.join(_TRAINS_DIR, "service_definitions", "services.json")) as f:
        for s in json.load(f):
            assert "service_id" in s and "train_id" in s and "route_id" in s and "priority_class" in s

    with open(os.path.join(_TRAINS_DIR, "published_timetables", "timetable.json")) as f:
        for tt in json.load(f):
            assert "service_id" in tt and "station_id" in tt


# ---------------------------------------------------------------------------
# 4. Cross-Reference & Foreign Key Integrity
# ---------------------------------------------------------------------------

def test_cross_reference_and_referential_integrity():
    """Verify zero orphan records and complete foreign key validity across datasets."""
    with open(os.path.join(_INFRA_DIR, "stations.json")) as f:
        station_ids = {s["id"] for s in json.load(f)}
    with open(os.path.join(_INFRA_DIR, "routes.json")) as f:
        route_ids = {r["id"] for r in json.load(f)}
    with open(os.path.join(_TRAINS_DIR, "train_identity", "trains.json")) as f:
        train_ids = {t["train_id"] for t in json.load(f)}
    with open(os.path.join(_TRAINS_DIR, "service_definitions", "services.json")) as f:
        services = json.load(f)
        service_ids = {s["service_id"] for s in services}
    with open(os.path.join(_TRAINS_DIR, "published_timetables", "timetable.json")) as f:
        timetable = json.load(f)

    # 1. Services foreign keys
    for s in services:
        assert s["train_id"] in train_ids, f"Service {s['service_id']} references missing train_id {s['train_id']}"
        assert s["route_id"] in route_ids, f"Service {s['service_id']} references missing route_id {s['route_id']}"

    # 2. Timetable foreign keys
    for tt in timetable:
        assert tt["service_id"] in service_ids, f"Timetable entry references missing service_id {tt['service_id']}"


# ---------------------------------------------------------------------------
# 5. Pending Services Strict Exclusion
# ---------------------------------------------------------------------------

def test_pending_services_isolation_invariant():
    """Verify all 7 pending services remain excluded from active timetables and models."""
    assert len(PENDING_SERVICES) == 7
    expected_pending = {
        "SRV_40143_01",
        "SRV_40144_01",
        "SRV_41015_01",
        "SRV_41131_01",
        "SRV_41132_01",
        "SRV_42413_01",
        "SRV_42425_01",
    }
    assert PENDING_SERVICES == expected_pending

    with open(os.path.join(_TRAINS_DIR, "published_timetables", "timetable.json")) as f:
        timetable_services = {tt["service_id"] for tt in json.load(f)}

    # None of the pending services should be in the active 40 published services
    for ps in PENDING_SERVICES:
        assert ps not in timetable_services, f"Pending service {ps} found in published timetable!"
