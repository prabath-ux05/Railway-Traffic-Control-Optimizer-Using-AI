# Phase 34 Evaluation v3: Time Resolution 2 (0.5 Minute / 30s) Analysis

## 1. Executive Summary

- **Time Resolution:** `2` (integer units of `0.5` minutes = 30 seconds)
- **Total Experiments Evaluated:** 45
- **Stored Negative-Savings Cases (Resolution 1):** 19
- **Negative-Savings Cases Becoming >= 0 (Resolution 2):** **19** of 19
- **Negative-Savings Cases Remaining Negative:** 0
- **Mean Solve Time:** 0.3416 s (vs stored 0.4396 s, ratio: 0.78x)
- **Max Solve Time:** 0.9 s (vs stored 1.4771 s)

## 2. Side-by-Side Comparison Table

| Experiment ID | Status | Stored FIFO (m) | v3 FIFO (m) | Stored CP-SAT (m) | v3 CP-SAT (m) | Stored Sav (m) | v3 Sav (m) | Stored Time (s) | v3 Time (s) | Became >= 0 |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| `EXP_31_1_01A_NOMINAL_MULTI` | OPTIMAL | 43.5 | 43.5 | 51.0 | 43.5 | -7.5 | 0.0 | 0.218 | 0.082 | **YES** |
| `EXP_31_1_01B_NOMINAL_WEST` | OPTIMAL | 116.0 | 116.0 | 116.0 | 116.0 | 0.0 | 0.0 | 0.184 | 0.112 | — |
| `EXP_31_1_02A_DEP_EXPRESS_WEST` | OPTIMAL | 208.0 | 208.0 | 133.0 | 133.0 | 75.0 | 75.0 | 0.100 | 0.067 | — |
| `EXP_31_1_02B_DEP_MULTI_CORRIDOR` | OPTIMAL | 227.5 | 227.5 | 102.0 | 94.5 | 125.5 | 133.0 | 0.068 | 0.068 | — |
| `EXP_31_1_03A_DWELL_JUNCTION_PER` | OPTIMAL | 104.0 | 104.0 | 104.0 | 104.0 | 0.0 | 0.0 | 0.101 | 0.069 | — |
| `EXP_31_1_03B_DWELL_JUNCTION_TBM` | OPTIMAL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.015 | 0.022 | — |
| `EXP_31_1_04A_TSR_THROAT_BBQ` | OPTIMAL | 107.0 | 107.0 | 107.0 | 107.0 | 0.0 | 0.0 | 0.089 | 0.073 | — |
| `EXP_31_1_04B_TSR_NORTH_TRUNK` | OPTIMAL | 7.0 | 7.0 | 22.0 | 7.0 | -15.0 | 0.0 | 0.053 | 0.052 | **YES** |
| `EXP_31_1_05A_BLOCK_PTMS_BRANCH` | OPTIMAL | 89.0 | 89.0 | 89.0 | 89.0 | 0.0 | 0.0 | 0.136 | 0.070 | — |
| `EXP_31_1_06A_JCT_BBQ_THROTTLE` | OPTIMAL | 114.0 | 114.0 | 114.0 | 114.0 | 0.0 | 0.0 | 0.115 | 0.087 | — |
| `EXP_31_1_06B_JCT_PAB_MERGE` | OPTIMAL | 34.0 | 34.0 | 34.0 | 34.0 | 0.0 | 0.0 | 0.114 | 0.066 | — |
| `EXP_31_1_07A_COMPOUND_WEST_THROAT` | OPTIMAL | 209.0 | 209.0 | 149.0 | 149.0 | 60.0 | 60.0 | 0.176 | 0.100 | — |
| `EXP_31_1_07B_COMPOUND_MULTI_CORRIDOR` | OPTIMAL | 262.0 | 262.0 | 149.0 | 149.0 | 113.0 | 113.0 | 0.105 | 0.070 | — |
| `EXP_SCALE_04_NOMINAL` | OPTIMAL | 35.5 | 35.5 | 43.0 | 35.5 | -7.5 | 0.0 | 0.084 | 0.066 | **YES** |
| `EXP_SCALE_08_NOMINAL` | OPTIMAL | 45.5 | 45.5 | 53.0 | 45.5 | -7.5 | 0.0 | 0.260 | 0.175 | **YES** |
| `EXP_SCALE_12_NOMINAL` | OPTIMAL | 127.5 | 127.5 | 135.0 | 127.5 | -7.5 | 0.0 | 0.381 | 0.302 | **YES** |
| `EXP_SCALE_16_NOMINAL` | OPTIMAL | 131.0 | 131.0 | 146.0 | 131.0 | -15.0 | 0.0 | 0.551 | 0.411 | **YES** |
| `EXP_SCALE_20_NOMINAL` | OPTIMAL | 133.0 | 133.0 | 148.0 | 133.0 | -15.0 | 0.0 | 0.676 | 0.480 | **YES** |
| `EXP_SCALE_30_NOMINAL` | OPTIMAL | 1781.0 | 1781.0 | 1793.0 | 1777.0 | -12.0 | 4.0 | 1.114 | 0.800 | **YES** |
| `EXP_SCALE_40_NOMINAL` | OPTIMAL | 1926.0 | 1926.0 | 1937.0 | 1921.0 | -11.0 | 5.0 | 1.319 | 0.862 | **YES** |
| `EXP_SCALE_04_COMPOUND` | OPTIMAL | 141.5 | 141.5 | 89.0 | 81.5 | 52.5 | 60.0 | 0.083 | 0.055 | — |
| `EXP_SCALE_08_COMPOUND` | OPTIMAL | 159.5 | 159.5 | 107.0 | 99.5 | 52.5 | 60.0 | 0.233 | 0.173 | — |
| `EXP_SCALE_12_COMPOUND` | OPTIMAL | 253.5 | 253.5 | 197.0 | 189.5 | 56.5 | 64.0 | 0.442 | 0.278 | — |
| `EXP_SCALE_16_COMPOUND` | OPTIMAL | 261.0 | 261.0 | 212.0 | 197.0 | 49.0 | 64.0 | 0.536 | 0.394 | — |
| `EXP_SCALE_20_COMPOUND` | OPTIMAL | 270.0 | 270.0 | 221.0 | 206.0 | 49.0 | 64.0 | 0.616 | 0.482 | — |
| `EXP_SCALE_30_COMPOUND` | OPTIMAL | 1951.0 | 1951.0 | 1895.0 | 1875.0 | 56.0 | 76.0 | 1.179 | 0.762 | — |
| `EXP_SCALE_40_COMPOUND` | OPTIMAL | 2127.5 | 2127.5 | 2066.0 | 2046.0 | 61.5 | 81.5 | 1.477 | 0.900 | — |
| `EXP_31_3_01_DEP_MILD` | OPTIMAL | 152.0 | 152.0 | 152.0 | 137.0 | 0.0 | 15.0 | 0.624 | 0.460 | — |
| `EXP_31_3_02_DEP_MOD` | OPTIMAL | 202.0 | 202.0 | 172.0 | 157.0 | 30.0 | 45.0 | 0.593 | 0.522 | — |
| `EXP_31_3_03_DEP_SEVERE` | OPTIMAL | 277.0 | 277.0 | 202.0 | 187.0 | 75.0 | 90.0 | 0.525 | 0.497 | — |
| `EXP_31_3_04_DWL_MILD` | OPTIMAL | 141.0 | 141.0 | 156.0 | 141.0 | -15.0 | 0.0 | 0.512 | 0.446 | **YES** |
| `EXP_31_3_05_DWL_MOD` | OPTIMAL | 156.0 | 156.0 | 171.0 | 156.0 | -15.0 | 0.0 | 0.519 | 0.436 | **YES** |
| `EXP_31_3_06_DWL_SEVERE` | OPTIMAL | 186.0 | 186.0 | 201.0 | 186.0 | -15.0 | 0.0 | 0.578 | 0.476 | **YES** |
| `EXP_31_3_07_TSR_MILD` | OPTIMAL | 170.0 | 170.0 | 181.0 | 166.0 | -11.0 | 4.0 | 0.504 | 0.477 | **YES** |
| `EXP_31_3_08_TSR_MOD` | OPTIMAL | 243.0 | 243.0 | 258.0 | 243.0 | -15.0 | 0.0 | 0.546 | 0.482 | **YES** |
| `EXP_31_3_09_TSR_SEVERE` | OPTIMAL | 438.0 | 438.0 | 432.0 | 417.0 | 6.0 | 21.0 | 0.501 | 0.490 | — |
| `EXP_31_3_10_BLK_MILD` | OPTIMAL | 133.0 | 133.0 | 148.0 | 133.0 | -15.0 | 0.0 | 0.554 | 0.474 | **YES** |
| `EXP_31_3_11_BLK_MOD` | OPTIMAL | 133.0 | 133.0 | 148.0 | 133.0 | -15.0 | 0.0 | 0.618 | 0.478 | **YES** |
| `EXP_31_3_12_BLK_SEVERE` | INFEASIBLE | 133.0 | 133.0 | N/A | N/A | N/A | N/A | 0.034 | 0.031 | — |
| `EXP_31_3_13_JCT_MILD` | OPTIMAL | 133.0 | 133.0 | 148.0 | 133.0 | -15.0 | 0.0 | 0.542 | 0.531 | **YES** |
| `EXP_31_3_14_JCT_MOD` | OPTIMAL | 133.0 | 133.0 | 148.0 | 133.0 | -15.0 | 0.0 | 0.517 | 0.515 | **YES** |
| `EXP_31_3_15_JCT_SEVERE` | OPTIMAL | 133.0 | 133.0 | 148.0 | 133.0 | -15.0 | 0.0 | 0.502 | 0.499 | **YES** |
| `EXP_31_3_16_CMP_MILD` | OPTIMAL | 195.0 | 195.0 | 191.0 | 176.0 | 4.0 | 19.0 | 0.546 | 0.502 | — |
| `EXP_31_3_17_CMP_MOD` | OPTIMAL | 318.0 | 318.0 | 288.0 | 273.0 | 30.0 | 45.0 | 0.506 | 0.496 | — |
| `EXP_31_3_18_CMP_SEVERE` | OPTIMAL | 573.0 | 573.0 | 477.0 | 462.0 | 96.0 | 111.0 | 0.636 | 0.484 | — |
