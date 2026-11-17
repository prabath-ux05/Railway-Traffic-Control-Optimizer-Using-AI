"""
scratch/run_phase34_4_benchmarks.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive Performance & Stress Benchmark Suite for Phase 34.4.
Measures timing breakdown across Simulation, Conflict Detection, FIFO Baseline,
CP-SAT Optimization, Decision-Support, and Total E2E pipeline for loads [4, 8, 12, 16, 20, 30, 40].
"""

import gc
import json
import os
import sys
import time
import tracemalloc
from typing import Any, Dict, List, Tuple

# Ensure project root in sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.pipeline import PipelineOrchestrator, _load_default_network
from evaluation.framework import PENDING_SERVICES
from evaluation.scalability_framework import (
    COHORT_4,
    COHORT_8,
    COHORT_12,
    COHORT_16,
    COHORT_20,
    COHORT_30,
    COHORT_40,
    SCALABILITY_COHORTS,
    SCALABILITY_LOAD_LEVELS,
    THROAT_TSR_SECTION,
    THROAT_TSR_TRAVEL_TIME,
    BBQ_JUNCTION_ID,
    BBQ_RESTRICTED_CAPACITY,
    PRIMARY_DELAY_SERVICE,
    PRIMARY_DEPARTURE_DELAY_MINUTES,
)
from optimization.scenarios import Scenario
from simulation.clock import SimulationClock, time_to_minutes
from simulation.conflicts import ConflictDetector
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState


def benchmark_e2e_components(
    orchestrator: PipelineOrchestrator,
    load_count: int,
    scenario_type: str,
) -> Dict[str, Any]:
    """Run detailed component-level profiling and E2E execution."""
    services = SCALABILITY_COHORTS[load_count]
    
    # 1. Setup scenario
    if scenario_type == "nominal":
        scen = Scenario(
            scenario_id=f"SCEN_P34_4_{load_count}_NOMINAL",
            name=f"Load {load_count} Nominal",
            affected_service_ids=services,
        )
    elif scenario_type == "departure_delay":
        scen = Scenario(
            scenario_id=f"SCEN_P34_4_{load_count}_DEP_DELAY",
            name=f"Load {load_count} Departure Delay",
            affected_service_ids=services,
            departure_delays={PRIMARY_DELAY_SERVICE: PRIMARY_DEPARTURE_DELAY_MINUTES},
        )
    elif scenario_type == "compound":
        scen = Scenario(
            scenario_id=f"SCEN_P34_4_{load_count}_COMPOUND",
            name=f"Load {load_count} Compound Disruption",
            affected_service_ids=services,
            departure_delays={PRIMARY_DELAY_SERVICE: PRIMARY_DEPARTURE_DELAY_MINUTES},
            track_speed_restrictions={THROAT_TSR_SECTION: THROAT_TSR_TRAVEL_TIME},
            junction_capacity_overrides={BBQ_JUNCTION_ID: BBQ_RESTRICTED_CAPACITY},
        )
    elif scenario_type == "throat_blockage":
        scen = Scenario(
            scenario_id=f"SCEN_P34_4_{load_count}_BLOCKED",
            name=f"Load {load_count} MAS-BBQ Throat Blockage",
            affected_service_ids=services,
            track_speed_restrictions={
                "MAS_BBQ_THROAT_SEGMENT_DOWN": 9999.0,
                "MAS_BBQ_THROAT_SEGMENT_UP": 9999.0,
            },
        )
    else:
        raise ValueError(f"Unknown scenario_type {scenario_type}")

    # Start memory tracing
    gc.collect()
    tracemalloc.start()
    
    t0 = time.perf_counter()
    
    # 1. Measure Simulation step
    t_sim_start = time.perf_counter()
    sim_clock = SimulationClock(start_time="00:00")
    state = SimulationState(clock=sim_clock)
    state.initialize_from_network(orchestrator.network)
    simulator = TrainSimulator(network=orchestrator.network, clock=sim_clock, state=state)
    
    for s_id in services:
        dep_delay = scen.departure_delays.get(s_id, 0.0)
        tt_entry = simulator.get_timetable_entry(s_id, orchestrator.network.services[s_id].origin)
        base_dep = time_to_minutes(tt_entry.departure) if tt_entry and tt_entry.departure else 360.0
        simulator.run_service_to_destination(
            s_id,
            start_time=base_dep + dep_delay,
            strict_track_lookup=False,
        )
    t_sim = time.perf_counter() - t_sim_start
    
    # Check completed services and resource cleanup in simulation state
    completed_services = len(state.train_states)
    stale_track_occupancies = sum(len(svcs) for svcs in state.track_occupancy.values())
    stale_resource_occupancies = len(state.resource_occupancy)
    
    # 2. Measure Conflict Detection step
    t_cd_start = time.perf_counter()
    conflicts = orchestrator.detector.detect_all(state=state)
    t_cd = time.perf_counter() - t_cd_start
    
    # 3. Measure Full Scenario comparison (FIFO Baseline & CP-SAT)
    t_opt_start = time.perf_counter()
    comparison = orchestrator.scenario_runner.run_scenario(
        scenario=scen,
        time_horizon=None,
    )
    t_opt = time.perf_counter() - t_opt_start
    
    # 4. Measure Decision Support Advisor step
    t_ds_start = time.perf_counter()
    assessment = orchestrator.advisor.evaluate_what_if_scenario(
        scenario=scen,
        service_ids=services,
    )
    t_ds = time.perf_counter() - t_ds_start
    
    t_total = time.perf_counter() - t0
    
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return {
        "load_count": load_count,
        "scenario_type": scenario_type,
        "solver_status": comparison.optimization_status,
        "solve_time_seconds": round(comparison.computation_time_seconds, 4),
        "sim_time_seconds": round(t_sim, 4),
        "conflict_detection_time_seconds": round(t_cd, 4),
        "opt_stage_time_seconds": round(t_opt, 4),
        "decision_support_time_seconds": round(t_ds, 4),
        "total_e2e_time_seconds": round(t_total, 4),
        "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
        "baseline_delay_min": round(comparison.baseline_total_delay, 2),
        "optimized_delay_min": round(comparison.optimized_total_delay, 2),
        "delay_savings_min": round(comparison.delay_savings_minutes, 2),
        "delay_savings_pct": round(comparison.delay_savings_percent, 2),
        "completed_services": completed_services,
        "stale_track_occupancies": stale_track_occupancies,
        "stale_resource_occupancies": stale_resource_occupancies,
        "conflict_count": len(conflicts),
        "recommendation_count": len(assessment.recommendations),
    }


def main():
    print("=" * 80)
    print("PHASE 34.4 PERFORMANCE & STRESS BENCHMARK RUNNER")
    print("=" * 80)
    
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)
    
    results = []
    
    # 1. Sweep all loads across Nominal, Departure Delay, and Compound Disruption
    scenario_modes = ["nominal", "departure_delay", "compound"]
    
    for mode in scenario_modes:
        print(f"\n>>> Running Scenario Mode: {mode.upper()}")
        for load in SCALABILITY_LOAD_LEVELS:
            res = benchmark_e2e_components(orch, load, mode)
            results.append(res)
            print(
                f"  Load {load:2d} | Status: {res['solver_status']:<10} | "
                f"Sim: {res['sim_time_seconds']:.3f}s | "
                f"CD: {res['conflict_detection_time_seconds']:.3f}s | "
                f"Solver: {res['solve_time_seconds']:.3f}s | "
                f"DS: {res['decision_support_time_seconds']:.3f}s | "
                f"Total E2E: {res['total_e2e_time_seconds']:.3f}s | "
                f"Peak Mem: {res['peak_memory_mb']:.2f}MB | "
                f"Svcs: {res['completed_services']}/{load} | "
                f"Stale: {res['stale_track_occupancies'] + res['stale_resource_occupancies']}"
            )
            
    # 2. Blockage scenario for key loads
    print(f"\n>>> Running Throat Blockage Scenario (Infeasible Case):")
    for load in [4, 10, 20, 40]:
        # For 10 services, use COHORT_12[:10]
        if load == 10:
            cohort_10 = list(COHORT_12[:10])
            SCALABILITY_COHORTS[10] = cohort_10
        res = benchmark_e2e_components(orch, load, "throat_blockage")
        results.append(res)
        print(
            f"  Load {load:2d} | Status: {res['solver_status']:<10} | "
            f"Sim: {res['sim_time_seconds']:.3f}s | "
            f"Solver: {res['solve_time_seconds']:.3f}s | "
            f"Total E2E: {res['total_e2e_time_seconds']:.3f}s | "
            f"Sav: {res['delay_savings_min']}m"
        )

    # 3. Multi-Run Repeatability Benchmark
    print(f"\n>>> Checking Multi-Run Timing & Hash Determinism at Load 40:")
    run1 = orch.run_pipeline(service_ids=COHORT_40)
    run2 = orch.run_pipeline(service_ids=COHORT_40)
    print(f"  Run 1 Hash: {run1.deterministic_hash} | Exec Time: {run1.execution_time_seconds:.3f}s")
    print(f"  Run 2 Hash: {run2.deterministic_hash} | Exec Time: {run2.execution_time_seconds:.3f}s")
    assert run1.deterministic_hash == run2.deterministic_hash, "Hash mismatch!"
    print("  -> Determinism Verified 100%!")

    output_path = os.path.join(_REPO_ROOT, "phase34_4_benchmark_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark results written to: {output_path}")


if __name__ == "__main__":
    main()
