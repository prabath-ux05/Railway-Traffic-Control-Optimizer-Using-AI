"""
scripts/generate_v2_evaluation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generates corrected evaluation datasets with opt-in apply_midnight_wrap=True,
stored separately in data/evaluation/v2/.

Leaves data/evaluation/ untouched to preserve CICT 2026 paper freeze reproducibility.
"""
import os
import sys
import json
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from optimization.scenarios import Scenario, ScenarioRunner
from evaluation.scalability_framework import (
    SCALABILITY_COHORTS,
    SCALABILITY_LOAD_LEVELS,
)

def generate_v2():
    v2_dir = os.path.join(repo_root, "data", "evaluation", "v2")
    os.makedirs(v2_dir, exist_ok=True)
    
    # 1. Evaluate nominal cohorts with and without midnight wrap
    runner = ScenarioRunner()
    cohort_results = {}
    v1_baselines = {}
    for n in [4, 8, 12, 16, 20, 30, 40]:
        services = SCALABILITY_COHORTS[n]
        scen = Scenario(
            scenario_id=f"SCEN_V2_NOMINAL_{n}",
            name=f"Load {n} Nominal State (v2 Day Wrap)",
            affected_service_ids=services,
        )
        comp_v1 = runner.run_scenario(scen, apply_midnight_wrap=False)
        v1_baselines[n] = comp_v1.baseline_total_delay

        comp_v2 = runner.run_scenario(scen, apply_midnight_wrap=True)
        cohort_results[n] = {
            "load_count": n,
            "services": services,
            "v1_baseline_delay_minutes": comp_v1.baseline_total_delay,
            "baseline_delay_minutes": comp_v2.baseline_total_delay,
            "optimized_delay_minutes": comp_v2.optimized_total_delay,
            "delay_savings_minutes": comp_v2.delay_savings_minutes,
            "delay_savings_percent": comp_v2.delay_savings_percent,
            "solver_status": comp_v2.optimization_status,
        }
        print(f"Cohort {n:2d}: v1 FIFO = {comp_v1.baseline_total_delay:.1f}m, v2 FIFO = {comp_v2.baseline_total_delay:.1f}m, v2 Opt = {comp_v2.optimized_total_delay:.1f}m")
        
    with open(os.path.join(v2_dir, "nominal_cohort_benchmarks.json"), "w", encoding="utf-8") as f:
        json.dump(cohort_results, f, indent=2)
        
    # 2. SRV_16159_01 detailed comparison
    scen_16159 = Scenario(
        scenario_id="SCEN_V2_SRV_16159",
        name="SRV_16159_01 Midnight Rollover Analysis",
        affected_service_ids=["SRV_16159_01"],
    )
    comp_v1 = runner.run_scenario(scen_16159, apply_midnight_wrap=False)
    comp_v2 = runner.run_scenario(scen_16159, apply_midnight_wrap=True)
    
    comparison_16159 = {
        "service_id": "SRV_16159_01",
        "description": "Mangalore Express (MS 23:10 -> TBM 23:40 -> CGL 00:08)",
        "v1_without_wrap": {
            "baseline_delay_minutes": comp_v1.baseline_total_delay,
            "optimized_delay_minutes": comp_v1.optimized_total_delay,
            "stops": [
                {
                    "station_id": a.station_id,
                    "original_arrival": a.original_arrival,
                    "original_departure": a.original_departure,
                    "adjusted_arrival": a.adjusted_arrival,
                    "adjusted_departure": a.adjusted_departure,
                    "delay_minutes": a.delay_minutes,
                }
                for a in comp_v1.feasible_baseline_result.adjusted_timetables.get("SRV_16159_01", [])
            ],
        },
        "v2_with_wrap": {
            "baseline_delay_minutes": comp_v2.baseline_total_delay,
            "optimized_delay_minutes": comp_v2.optimized_total_delay,
            "stops": [
                {
                    "station_id": a.station_id,
                    "original_arrival": a.original_arrival,
                    "original_departure": a.original_departure,
                    "adjusted_arrival": a.adjusted_arrival,
                    "adjusted_departure": a.adjusted_departure,
                    "delay_minutes": a.delay_minutes,
                }
                for a in comp_v2.feasible_baseline_result.adjusted_timetables.get("SRV_16159_01", [])
            ],
        },
    }
    with open(os.path.join(v2_dir, "midnight_wrap_comparison.json"), "w", encoding="utf-8") as f:
        json.dump(comparison_16159, f, indent=2)

    # 3. Write summary report markdown in v2
    md_content = f"""# Railway Traffic Optimizer: v2 Evaluation Results (Midnight Day-Wrap Corrected)

> **Dataset Scope:** Chennai Division Railway Traffic Optimizer
> **Mode:** Opt-in `apply_midnight_wrap = True` (+1440 day offset for post-midnight arrivals)
> **Baseline Status:** Preserved separately in `data/evaluation/` for frozen CICT 2026 paper reproduction.

## 1. Summary of Correction
In the published timetable, `SRV_16159_01` departs Chennai Egmore (MS) at `23:10` (1390.0m) and arrives at Chengalpattu (CGL) at `00:08` the following calendar day.
- **v1 Baseline (Unwrapped):** CGL arrival is treated as 8.0 min from midnight, introducing 1,415.0 min of artificial delay.
- **v2 Corrected (Wrapped):** CGL arrival is offset to 1,448.0 min, reducing artificial baseline delay to 0.0 min.

## 2. Nominal Cohort Performance Comparison

| Cohort Size | v1 Baseline Delay (min) | v2 Baseline Delay (min) | v2 Optimized Delay (min) | Artificial Delay Removed (min) |
|---|---|---|---|---|
| 4 Services | {v1_baselines[4]:.1f} | {cohort_results[4]['baseline_delay_minutes']:.1f} | {cohort_results[4]['optimized_delay_minutes']:.1f} | {v1_baselines[4] - cohort_results[4]['baseline_delay_minutes']:.1f} |
| 8 Services | {v1_baselines[8]:.1f} | {cohort_results[8]['baseline_delay_minutes']:.1f} | {cohort_results[8]['optimized_delay_minutes']:.1f} | {v1_baselines[8] - cohort_results[8]['baseline_delay_minutes']:.1f} |
| 12 Services | {v1_baselines[12]:.1f} | {cohort_results[12]['baseline_delay_minutes']:.1f} | {cohort_results[12]['optimized_delay_minutes']:.1f} | {v1_baselines[12] - cohort_results[12]['baseline_delay_minutes']:.1f} |
| 16 Services | {v1_baselines[16]:.1f} | {cohort_results[16]['baseline_delay_minutes']:.1f} | {cohort_results[16]['optimized_delay_minutes']:.1f} | {v1_baselines[16] - cohort_results[16]['baseline_delay_minutes']:.1f} |
| 20 Services | {v1_baselines[20]:.1f} | {cohort_results[20]['baseline_delay_minutes']:.1f} | {cohort_results[20]['optimized_delay_minutes']:.1f} | {v1_baselines[20] - cohort_results[20]['baseline_delay_minutes']:.1f} |
| 30 Services | {v1_baselines[30]:.1f} | {cohort_results[30]['baseline_delay_minutes']:.1f} | {cohort_results[30]['optimized_delay_minutes']:.1f} | {v1_baselines[30] - cohort_results[30]['baseline_delay_minutes']:.1f} |
| 40 Services | {v1_baselines[40]:.1f} | {cohort_results[40]['baseline_delay_minutes']:.1f} | {cohort_results[40]['optimized_delay_minutes']:.1f} | {v1_baselines[40] - cohort_results[40]['baseline_delay_minutes']:.1f} |
"""
    with open(os.path.join(v2_dir, "v2_evaluation_report.md"), "w", encoding="utf-8") as f:
        f.write(md_content)
    print("Successfully generated data/evaluation/v2/ evaluation results.")

if __name__ == "__main__":
    generate_v2()
