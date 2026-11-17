"""
scratch/run_phase31_4.py
~~~~~~~~~~~~~~~~~~~~~~~~
Executes Phase 31.4 comparative analysis consolidation and exports
both JSON results and Markdown summary.
"""

import os
import sys
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from evaluation.comparative_analysis import run_comparative_analysis

print("Starting Phase 31.4 Comparative Analysis...")
t0 = time.time()
result = run_comparative_analysis(time_limit_seconds=15.0)
t_elapsed = time.time() - t0

print(f"\nPhase 31.4 completed in {t_elapsed:.2f} seconds.")
print(f"Total experiments: {result.total_experiments}")
print(f"Feasible records: {len(result.feasible_records)}")
print(f"Infeasible records: {len(result.infeasible_records)}")
print(f"Phase 31.1 count: {len(result.phase31_1_records)}")
print(f"Phase 31.2 nominal count: {len(result.phase31_2_nominal_records)}")
print(f"Phase 31.2 compound count: {len(result.phase31_2_compound_records)}")
print(f"Phase 31.3 count: {len(result.phase31_3_records)}")

# Export JSON
json_path = os.path.join(repo_root, "data", "evaluation", "comparative_analysis_results.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
result.export_json(json_path)
print(f"Exported JSON to: {json_path} ({os.path.getsize(json_path)} bytes)")

# Generate Markdown
md_content = result.generate_markdown()
md_path = os.path.join(repo_root, "data", "evaluation", "phase31_4_report.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)
print(f"Exported Markdown to: {md_path} ({len(md_content)} chars)")

if result.global_delay_stats_total:
    print("\nGlobal Total Delay Savings:")
    print(f"  Mean Savings: {result.global_delay_stats_total.savings_min_stats.get('mean')} min")
    print(f"  Median Savings: {result.global_delay_stats_total.savings_min_stats.get('median')} min")
    print(f"  Mean Savings %: {result.global_delay_stats_total.savings_pct_stats.get('mean')}%")

if result.global_solver_stats:
    print("\nGlobal Solver Stats:")
    print(f"  Optimal Rate: {result.global_solver_stats.optimal_rate_pct}%")
    print(f"  Mean Solve Time: {result.global_solver_stats.solve_time_stats.get('mean')} s")
