# Railway Traffic Optimizer: v2 Evaluation Results (Midnight Day-Wrap Corrected)

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
| 4 Services | 35.5 | 35.5 | 43.0 | 0.0 |
| 8 Services | 45.5 | 45.5 | 53.0 | 0.0 |
| 12 Services | 127.5 | 127.5 | 135.0 | 0.0 |
| 16 Services | 131.0 | 131.0 | 146.0 | 0.0 |
| 20 Services | 133.0 | 133.0 | 148.0 | 0.0 |
| 30 Services | 1781.0 | 366.0 | 378.0 | 1415.0 |
| 40 Services | 1926.0 | 511.0 | 522.0 | 1415.0 |
