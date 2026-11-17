"""
scratch/run_phase32_2.py
~~~~~~~~~~~~~~~~~~~~~~~~
Executes Phase 32.2 Delay Propagation Analytics and exports
JSON dataset and Markdown report.
"""

import os
import sys
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from evaluation.delay_propagation_analytics import run_delay_propagation_analytics

print("Starting Phase 32.2 Delay Propagation Analytics...")
t0 = time.time()
analytics = run_delay_propagation_analytics(time_limit_seconds=15.0)
t_elapsed = time.time() - t0

print(f"\nPhase 32.2 completed in {t_elapsed:.2f} seconds.")
print(f"Total services profiled: {analytics.total_services_profiled}")
print(f"Mean knock-on multiplier: {analytics.mean_knock_on_multiplier:.2f}x")
print(f"Overall network damping efficiency: {analytics.overall_damping_efficiency_pct:.1f}%")
print(f"Propagation chains traced: {len(analytics.propagation_chains)}")
print(f"Corridor profiles generated: {len(analytics.corridor_profiles)}")

# Export JSON
json_path = os.path.join(repo_root, "data", "evaluation", "delay_propagation_analytics.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
analytics.export_json(json_path)
print(f"Exported JSON to: {json_path} ({os.path.getsize(json_path)} bytes)")

# Export Markdown
md_path = os.path.join(repo_root, "data", "evaluation", "phase32_2_report.md")
md_content = analytics.generate_markdown()
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)
print(f"Exported Markdown to: {md_path} ({len(md_content)} chars)")
