"""
scripts/run_v3_evaluation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Executes all 45 stored research experiments at time_resolution = 2 (0.5 minute / 30s)
and writes side-by-side comparative results to data/evaluation/v3/.

Never overwrites stored paper files in data/evaluation/.
"""

import json
import os
import sys
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from typing import Any, Dict, List

from evaluation.comparative_analysis import ComparativeAnalyzer


def run_v3_evaluation(base_dir: str):
    v3_dir = os.path.join(base_dir, "data", "evaluation", "v3")
    os.makedirs(v3_dir, exist_ok=True)

    # 1. Load stored baseline experiments
    stored_path = os.path.join(base_dir, "data", "evaluation", "comparative_analysis_results.json")
    with open(stored_path, "r", encoding="utf-8") as f:
        stored_data = json.load(f)

    stored_records = {r["experiment_id"]: r for r in stored_data.get("all_records", [])}
    print(f"[INFO] Loaded {len(stored_records)} stored experiment records from {stored_path}")

    # 2. Run all 45 experiments at time_resolution=2
    print("[INFO] Executing all 45 experiments at time_resolution=2...")
    t0 = time.time()
    analyzer = ComparativeAnalyzer(time_resolution=2)
    v3_result = analyzer.run()
    elapsed = time.time() - t0
    print(f"[INFO] Execution completed in {elapsed:.2f} seconds.")

    v3_records = {r.experiment_id: r for r in v3_result.all_records}

    # 3. Side-by-side comparison
    comparisons: List[Dict[str, Any]] = []
    neg_to_non_neg_count = 0
    total_negative_in_stored = 0

    solve_times_stored = []
    solve_times_v3 = []

    for exp_id, s_rec in stored_records.items():
        v_rec = v3_records.get(exp_id)
        if not v_rec:
            continue

        s_savings = s_rec.get("delay_savings_min")
        v_savings = v_rec.delay_savings_min

        s_is_neg = s_savings is not None and s_savings < -1e-6
        if s_is_neg:
            total_negative_in_stored += 1

        v_is_non_neg = v_savings is not None and v_savings >= -1e-6
        became_non_neg = s_is_neg and v_is_non_neg
        if became_non_neg:
            neg_to_non_neg_count += 1

        s_solve = s_rec.get("solve_time_seconds")
        v_solve = v_rec.solve_time_seconds
        if s_solve is not None:
            solve_times_stored.append(s_solve)
        if v_solve is not None:
            solve_times_v3.append(v_solve)

        comparisons.append({
            "experiment_id": exp_id,
            "source_phase": s_rec.get("source_phase"),
            "is_feasible": v_rec.is_feasible,
            "solver_status": v_rec.solver_status,
            "stored_fifo_total_delay_min": s_rec.get("fifo_total_delay_min"),
            "v3_fifo_total_delay_min": v_rec.fifo_total_delay_min,
            "stored_cpsat_total_delay_min": s_rec.get("cpsat_total_delay_min"),
            "v3_cpsat_total_delay_min": v_rec.cpsat_total_delay_min,
            "stored_savings_min": s_savings,
            "v3_savings_min": v_savings,
            "stored_savings_pct": s_rec.get("delay_savings_pct"),
            "v3_savings_pct": v_rec.delay_savings_pct,
            "stored_solve_time_seconds": s_solve,
            "v3_solve_time_seconds": v_solve,
            "stored_was_negative": s_is_neg,
            "v3_is_non_negative": v_is_non_neg,
            "became_non_negative": became_non_neg,
        })

    # Summary statistics
    stored_mean_solve = sum(solve_times_stored) / len(solve_times_stored) if solve_times_stored else 0.0
    stored_max_solve = max(solve_times_stored) if solve_times_stored else 0.0
    v3_mean_solve = sum(solve_times_v3) / len(solve_times_v3) if solve_times_v3 else 0.0
    v3_max_solve = max(solve_times_v3) if solve_times_v3 else 0.0

    summary = {
        "total_experiments": len(comparisons),
        "time_resolution": 2,
        "time_step_unit": "0.5 minute (30 seconds)",
        "total_negative_savings_cases_stored": total_negative_in_stored,
        "negative_cases_becoming_non_negative": neg_to_non_neg_count,
        "negative_cases_remaining_negative": total_negative_in_stored - neg_to_non_neg_count,
        "solve_time_cost": {
            "stored_resolution_1_mean_seconds": round(stored_mean_solve, 4),
            "stored_resolution_1_max_seconds": round(stored_max_solve, 4),
            "v3_resolution_2_mean_seconds": round(v3_mean_solve, 4),
            "v3_resolution_2_max_seconds": round(v3_max_solve, 4),
            "mean_solve_time_ratio": round(v3_mean_solve / stored_mean_solve, 2) if stored_mean_solve > 0 else 1.0,
        },
    }

    output_data = {
        "summary": summary,
        "comparisons": comparisons,
    }

    # 4. Save JSON
    json_path = os.path.join(v3_dir, "comparative_analysis_v3.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"[INFO] Wrote JSON to {json_path}")

    # 5. Save Markdown report
    md_path = os.path.join(v3_dir, "v3_evaluation_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Phase 34 Evaluation v3: Time Resolution 2 (0.5 Minute / 30s) Analysis\n\n")
        f.write("## 1. Executive Summary\n\n")
        f.write(f"- **Time Resolution:** `2` (integer units of `0.5` minutes = 30 seconds)\n")
        f.write(f"- **Total Experiments Evaluated:** {summary['total_experiments']}\n")
        f.write(f"- **Stored Negative-Savings Cases (Resolution 1):** {summary['total_negative_savings_cases_stored']}\n")
        f.write(f"- **Negative-Savings Cases Becoming >= 0 (Resolution 2):** **{summary['negative_cases_becoming_non_negative']}** of {summary['total_negative_savings_cases_stored']}\n")
        f.write(f"- **Negative-Savings Cases Remaining Negative:** {summary['negative_cases_remaining_negative']}\n")
        f.write(f"- **Mean Solve Time:** {summary['solve_time_cost']['v3_resolution_2_mean_seconds']} s (vs stored {summary['solve_time_cost']['stored_resolution_1_mean_seconds']} s, ratio: {summary['solve_time_cost']['mean_solve_time_ratio']}x)\n")
        f.write(f"- **Max Solve Time:** {summary['solve_time_cost']['v3_resolution_2_max_seconds']} s (vs stored {summary['solve_time_cost']['stored_resolution_1_max_seconds']} s)\n\n")

        f.write("## 2. Side-by-Side Comparison Table\n\n")
        f.write("| Experiment ID | Status | Stored FIFO (m) | v3 FIFO (m) | Stored CP-SAT (m) | v3 CP-SAT (m) | Stored Sav (m) | v3 Sav (m) | Stored Time (s) | v3 Time (s) | Became >= 0 |\n")
        f.write("|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|\n")
        for c in comparisons:
            st_f = f"{c['stored_fifo_total_delay_min']:.1f}" if c['stored_fifo_total_delay_min'] is not None else "N/A"
            v3_f = f"{c['v3_fifo_total_delay_min']:.1f}" if c['v3_fifo_total_delay_min'] is not None else "N/A"
            st_c = f"{c['stored_cpsat_total_delay_min']:.1f}" if c['stored_cpsat_total_delay_min'] is not None else "N/A"
            v3_c = f"{c['v3_cpsat_total_delay_min']:.1f}" if c['v3_cpsat_total_delay_min'] is not None else "N/A"
            st_s = f"{c['stored_savings_min']:.1f}" if c['stored_savings_min'] is not None else "N/A"
            v3_s = f"{c['v3_savings_min']:.1f}" if c['v3_savings_min'] is not None else "N/A"
            st_t = f"{c['stored_solve_time_seconds']:.3f}" if c['stored_solve_time_seconds'] is not None else "N/A"
            v3_t = f"{c['v3_solve_time_seconds']:.3f}" if c['v3_solve_time_seconds'] is not None else "N/A"
            chg = "**YES**" if c['became_non_negative'] else ("—" if not c['stored_was_negative'] else "NO")
            f.write(f"| `{c['experiment_id']}` | {c['solver_status']} | {st_f} | {v3_f} | {st_c} | {v3_c} | {st_s} | {v3_s} | {st_t} | {v3_t} | {chg} |\n")

    print(f"[INFO] Wrote Markdown to {md_path}")
    print("\n" + "=" * 80)
    print("V3 RESOLUTION 2 SUMMARY:")
    print(f"  Total experiments: {summary['total_experiments']}")
    print(f"  Stored negative-savings cases: {summary['total_negative_savings_cases_stored']}")
    print(f"  Cases becoming >= 0 at resolution 2: {summary['negative_cases_becoming_non_negative']}")
    print(f"  Stored mean solve time: {summary['solve_time_cost']['stored_resolution_1_mean_seconds']} s")
    print(f"  v3 mean solve time:     {summary['solve_time_cost']['v3_resolution_2_mean_seconds']} s (ratio: {summary['solve_time_cost']['mean_solve_time_ratio']}x)")
    print(f"  Stored max solve time:  {summary['solve_time_cost']['stored_resolution_1_max_seconds']} s")
    print(f"  v3 max solve time:      {summary['solve_time_cost']['v3_resolution_2_max_seconds']} s")
    print("=" * 80)


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run_v3_evaluation(repo_root)
