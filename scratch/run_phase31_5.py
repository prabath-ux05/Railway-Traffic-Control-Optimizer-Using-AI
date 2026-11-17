"""
scratch/run_phase31_5.py
~~~~~~~~~~~~~~~~~~~~~~~~
Executes Phase 31.5 full research metrics consolidation and exports
JSON dataset and Markdown report.
"""

import os
import sys
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from evaluation.metrics_consolidation import run_metrics_consolidation

print("Starting Phase 31.5 Research Metrics Consolidation...")
t0 = time.time()
consolidated = run_metrics_consolidation(time_limit_seconds=15.0)
t_elapsed = time.time() - t0

print(f"\nPhase 31.5 completed in {t_elapsed:.2f} seconds.")
kpi = consolidated.kpi_summary
print(f"Total experiments: {kpi.n_total_experiments}")
print(f"Feasible runs: {kpi.n_feasible_experiments}")
print(f"Infeasible boundaries: {kpi.n_infeasible_experiments}")
print(f"Mean Delay Savings: +{kpi.mean_delay_savings_min:.2f} min (Max: +{kpi.max_delay_savings_min:.2f} min)")
print(f"Conflict Resolution Rate: {kpi.overall_conflict_resolution_rate_pct:.2f}%")
print(f"Optimality Rate: {kpi.optimality_rate_pct:.2f}% (Mean solve time: {kpi.mean_solve_time_seconds:.3f} s)")

# Export JSON
json_path = os.path.join(repo_root, "data", "evaluation", "consolidated_research_metrics.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
consolidated.export_json(json_path)
print(f"Exported JSON to: {json_path} ({os.path.getsize(json_path)} bytes)")

# Export Markdown
md_path = os.path.join(repo_root, "data", "evaluation", "phase31_5_report.md")
md_content = consolidated.generate_markdown()
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)
print(f"Exported Markdown to: {md_path} ({len(md_content)} chars)")
