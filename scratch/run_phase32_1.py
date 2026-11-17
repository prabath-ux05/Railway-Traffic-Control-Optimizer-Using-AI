"""
scratch/run_phase32_1.py
~~~~~~~~~~~~~~~~~~~~~~~~
Executes Phase 32.1 Bottleneck & Resource Analytics and exports
JSON dataset and Markdown report.
"""

import os
import sys
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from evaluation.bottleneck_analytics import run_bottleneck_analytics

print("Starting Phase 32.1 Bottleneck & Resource Analytics...")
t0 = time.time()
analytics = run_bottleneck_analytics(time_limit_seconds=15.0)
t_elapsed = time.time() - t0

print(f"\nPhase 32.1 completed in {t_elapsed:.2f} seconds.")
print(f"Total resources profiled: {analytics.total_resources_analyzed}")
print(f"Ranked bottlenecks identified: {len(analytics.ranked_bottlenecks)}")
print(f"Corridors profiled: {len(analytics.corridor_utilizations)}")
print(f"Junctions profiled: {len(analytics.junction_utilizations)}")
print(f"Platforms profiled: {len(analytics.platform_utilizations)}")

print("\nTop 3 Ranked Bottlenecks:")
for b in analytics.ranked_bottlenecks[:3]:
    print(f"  Rank {b.rank}: {b.resource_name} (BSI: {b.bottleneck_severity_index:.1f}, Type: {b.bottleneck_type.value})")

# Export JSON
json_path = os.path.join(repo_root, "data", "evaluation", "bottleneck_analytics_results.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
analytics.export_json(json_path)
print(f"Exported JSON to: {json_path} ({os.path.getsize(json_path)} bytes)")

# Export Markdown
md_path = os.path.join(repo_root, "data", "evaluation", "phase32_1_report.md")
md_content = analytics.generate_markdown()
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)
print(f"Exported Markdown to: {md_path} ({len(md_content)} chars)")
