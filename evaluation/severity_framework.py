"""
evaluation/severity_framework.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 31.3 — Disruption Severity Experiments for Chennai Division Railway Traffic Optimizer.

Evaluates how the CP-SAT optimizer and Feasible Baseline scheduler behave when subjected
to increasing disruption severity across all 6 standardized disruption classes:
1. Departure Delays at origin terminals (mild / moderate / severe)
2. Station Dwell Delays at intermediate stops (mild / moderate / severe)
3. Temporary Speed Restrictions (TSR) (mild / moderate / severe)
4. Blocked Track Sections (mild / moderate / severe)
5. Junction & Throat Contention (mild / moderate / severe)
6. Compound Multi-Corridor Disruptions (mild / moderate / severe)

Features:
- Fixed, deterministic service cohort (COHORT_20 from Phase 31.2) spanning all 5 operational corridors.
- Strict exclusion of all 7 pending services.
- Deterministic, documented simulation parameters for each severity level.
- Measures direct vs. propagated delay, peak delay, FIFO vs. CP-SAT savings, conflict resolution,
  throughput, CP-SAT solve time, resource utilization, and feasibility boundaries / inflection points.
- SHA-256 config and result hash verification for absolute determinism.
- Zero mutation of published timetables, train records, or network topology.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from optimization.scenarios import Scenario
from simulation.network import Network
from evaluation.framework import (
    ExperimentGroupType,
    PENDING_SERVICES,
    ResearchExperimentConfig,
    ResearchExperimentResult,
    ResearchExperimentRunner,
    ResearchMetrics,
)
from evaluation.scalability_framework import COHORT_20


# ---------------------------------------------------------------------------
# Enums for Disruption Class and Severity Level
# ---------------------------------------------------------------------------

class DisruptionClass(str, Enum):
    """Six standardized disruption classes for severity evaluation."""
    DEPARTURE_DELAY = "DEPARTURE_DELAY"
    DWELL_DELAY = "DWELL_DELAY"
    SPEED_RESTRICTION = "SPEED_RESTRICTION"
    BLOCKED_SECTION = "BLOCKED_SECTION"
    JUNCTION_CONTENTION = "JUNCTION_CONTENTION"
    COMPOUND_DISRUPTION = "COMPOUND_DISRUPTION"


class SeverityLevel(str, Enum):
    """Three standardized severity tiers."""
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


# ---------------------------------------------------------------------------
# Experiment Specification Dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SeverityExperimentSpec:
    """Deterministic specification for a severity test experiment."""
    disruption_class: DisruptionClass
    severity_level: SeverityLevel
    experiment_id: str
    name: str
    description: str
    group_type: ExperimentGroupType
    scenario_id: str
    scenario_name: str
    scenario_description: str
    time_horizon: Tuple[float, float]
    # Parameter details for auditability and reporting
    parameter_summary: str
    primary_target: str
    departure_delays: Dict[str, float] = field(default_factory=dict)
    station_delays: Dict[str, Dict[str, float]] = field(default_factory=dict)
    track_speed_restrictions: Dict[str, float] = field(default_factory=dict)
    blocked_sections: List[str] = field(default_factory=list)
    junction_capacity_overrides: Dict[str, int] = field(default_factory=dict)

    def create_scenario(self, cohort: List[str]) -> Scenario:
        """Instantiate a clean Scenario instance for this spec."""
        return Scenario(
            scenario_id=self.scenario_id,
            name=self.scenario_name,
            description=self.scenario_description,
            affected_service_ids=list(cohort),
            departure_delays=copy.deepcopy(self.departure_delays),
            station_delays=copy.deepcopy(self.station_delays),
            track_speed_restrictions=copy.deepcopy(self.track_speed_restrictions),
            blocked_sections=list(self.blocked_sections),
            junction_capacity_overrides=copy.deepcopy(self.junction_capacity_overrides),
        )

    def create_config(self, cohort: List[str], time_limit_seconds: float = 15.0) -> ResearchExperimentConfig:
        """Instantiate a standard ResearchExperimentConfig for this spec."""
        return ResearchExperimentConfig(
            experiment_id=self.experiment_id,
            group=self.group_type,
            name=self.name,
            description=self.description,
            scenario=self.create_scenario(cohort),
            target_service_ids=list(cohort),
            time_horizon=self.time_horizon,
            time_limit_seconds=time_limit_seconds,
        )


# ---------------------------------------------------------------------------
# 18 Standardized Severity Experiment Specifications
# ---------------------------------------------------------------------------

SEVERITY_EXPERIMENT_SPECS: Dict[Tuple[DisruptionClass, SeverityLevel], SeverityExperimentSpec] = {
    # -----------------------------------------------------------------------
    # 1. Departure Delay
    # -----------------------------------------------------------------------
    (DisruptionClass.DEPARTURE_DELAY, SeverityLevel.MILD): SeverityExperimentSpec(
        disruption_class=DisruptionClass.DEPARTURE_DELAY,
        severity_level=SeverityLevel.MILD,
        experiment_id="EXP_31_3_01_DEP_MILD",
        name="Departure Delay - Mild (+5m)",
        description="Minor 5-minute origin departure delay on Lalbagh SF Express 12607 at MAS.",
        group_type=ExperimentGroupType.DEPARTURE_DELAY,
        scenario_id="SCEN_31_3_DEP_MILD",
        scenario_name="12607 MAS 5m Departure Delay",
        scenario_description="Origin departure delay of 5 minutes on SRV_12607_01.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Departure delay: +5.0 min at MAS",
        primary_target="SRV_12607_01 (MAS origin)",
        departure_delays={"SRV_12607_01": 5.0},
    ),
    (DisruptionClass.DEPARTURE_DELAY, SeverityLevel.MODERATE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.DEPARTURE_DELAY,
        severity_level=SeverityLevel.MODERATE,
        experiment_id="EXP_31_3_02_DEP_MOD",
        name="Departure Delay - Moderate (+15m)",
        description="Moderate 15-minute origin departure delay on Lalbagh SF Express 12607 at MAS.",
        group_type=ExperimentGroupType.DEPARTURE_DELAY,
        scenario_id="SCEN_31_3_DEP_MOD",
        scenario_name="12607 MAS 15m Departure Delay",
        scenario_description="Origin departure delay of 15 minutes on SRV_12607_01.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Departure delay: +15.0 min at MAS",
        primary_target="SRV_12607_01 (MAS origin)",
        departure_delays={"SRV_12607_01": 15.0},
    ),
    (DisruptionClass.DEPARTURE_DELAY, SeverityLevel.SEVERE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.DEPARTURE_DELAY,
        severity_level=SeverityLevel.SEVERE,
        experiment_id="EXP_31_3_03_DEP_SEVERE",
        name="Departure Delay - Severe (+30m)",
        description="Substantial 30-minute origin departure delay on Lalbagh SF Express 12607 at MAS.",
        group_type=ExperimentGroupType.DEPARTURE_DELAY,
        scenario_id="SCEN_31_3_DEP_SEVERE",
        scenario_name="12607 MAS 30m Departure Delay",
        scenario_description="Origin departure delay of 30 minutes on SRV_12607_01.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Departure delay: +30.0 min at MAS",
        primary_target="SRV_12607_01 (MAS origin)",
        departure_delays={"SRV_12607_01": 30.0},
    ),

    # -----------------------------------------------------------------------
    # 2. Station Dwell Delay
    # -----------------------------------------------------------------------
    (DisruptionClass.DWELL_DELAY, SeverityLevel.MILD): SeverityExperimentSpec(
        disruption_class=DisruptionClass.DWELL_DELAY,
        severity_level=SeverityLevel.MILD,
        experiment_id="EXP_31_3_04_DWL_MILD",
        name="Station Dwell Delay - Mild (+5m at PER)",
        description="Minor 5-minute extended passenger boarding dwell at Perambur (PER).",
        group_type=ExperimentGroupType.DWELL_DELAY,
        scenario_id="SCEN_31_3_DWL_MILD",
        scenario_name="PER Intermediate Dwell Extension (+5m)",
        scenario_description="Station dwell delay of 5 minutes at PER on SRV_12607_01 and SRV_43411_01.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Station dwell delay: +5.0 min at PER",
        primary_target="PER station (SRV_12607_01, SRV_43411_01)",
        station_delays={"SRV_12607_01": {"PER": 5.0}, "SRV_43411_01": {"PER": 5.0}},
    ),
    (DisruptionClass.DWELL_DELAY, SeverityLevel.MODERATE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.DWELL_DELAY,
        severity_level=SeverityLevel.MODERATE,
        experiment_id="EXP_31_3_05_DWL_MOD",
        name="Station Dwell Delay - Moderate (+10m at PER)",
        description="Moderate 10-minute extended passenger boarding dwell at Perambur (PER).",
        group_type=ExperimentGroupType.DWELL_DELAY,
        scenario_id="SCEN_31_3_DWL_MOD",
        scenario_name="PER Intermediate Dwell Extension (+10m)",
        scenario_description="Station dwell delay of 10 minutes at PER on SRV_12607_01 and SRV_43411_01.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Station dwell delay: +10.0 min at PER",
        primary_target="PER station (SRV_12607_01, SRV_43411_01)",
        station_delays={"SRV_12607_01": {"PER": 10.0}, "SRV_43411_01": {"PER": 10.0}},
    ),
    (DisruptionClass.DWELL_DELAY, SeverityLevel.SEVERE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.DWELL_DELAY,
        severity_level=SeverityLevel.SEVERE,
        experiment_id="EXP_31_3_06_DWL_SEVERE",
        name="Station Dwell Delay - Severe (+20m at PER)",
        description="Significant 20-minute extended dwell at Perambur (PER).",
        group_type=ExperimentGroupType.DWELL_DELAY,
        scenario_id="SCEN_31_3_DWL_SEVERE",
        scenario_name="PER Intermediate Dwell Extension (+20m)",
        scenario_description="Station dwell delay of 20 minutes at PER on SRV_12607_01 and SRV_43411_01.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Station dwell delay: +20.0 min at PER",
        primary_target="PER station (SRV_12607_01, SRV_43411_01)",
        station_delays={"SRV_12607_01": {"PER": 20.0}, "SRV_43411_01": {"PER": 20.0}},
    ),

    # -----------------------------------------------------------------------
    # 3. Temporary Speed Restrictions (TSR)
    # -----------------------------------------------------------------------
    (DisruptionClass.SPEED_RESTRICTION, SeverityLevel.MILD): SeverityExperimentSpec(
        disruption_class=DisruptionClass.SPEED_RESTRICTION,
        severity_level=SeverityLevel.MILD,
        experiment_id="EXP_31_3_07_TSR_MILD",
        name="Speed Restriction - Mild (8m on Throat)",
        description="Caution order on MAS-BBQ throat increasing traversal time from 4m to 8m (2.0x).",
        group_type=ExperimentGroupType.SPEED_RESTRICTION,
        scenario_id="SCEN_31_3_TSR_MILD",
        scenario_name="MAS-BBQ Throat TSR 8m",
        scenario_description="Track speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN set to 8.0 minutes.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Travel time: 8.0 min (+4.0 min, 2.0x normal)",
        primary_target="MAS_BBQ_THROAT_SEGMENT_DOWN",
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0},
    ),
    (DisruptionClass.SPEED_RESTRICTION, SeverityLevel.MODERATE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.SPEED_RESTRICTION,
        severity_level=SeverityLevel.MODERATE,
        experiment_id="EXP_31_3_08_TSR_MOD",
        name="Speed Restriction - Moderate (15m on Throat)",
        description="Caution order on MAS-BBQ throat increasing traversal time from 4m to 15m (3.75x).",
        group_type=ExperimentGroupType.SPEED_RESTRICTION,
        scenario_id="SCEN_31_3_TSR_MOD",
        scenario_name="MAS-BBQ Throat TSR 15m",
        scenario_description="Track speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN set to 15.0 minutes.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Travel time: 15.0 min (+11.0 min, 3.75x normal)",
        primary_target="MAS_BBQ_THROAT_SEGMENT_DOWN",
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 15.0},
    ),
    (DisruptionClass.SPEED_RESTRICTION, SeverityLevel.SEVERE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.SPEED_RESTRICTION,
        severity_level=SeverityLevel.SEVERE,
        experiment_id="EXP_31_3_09_TSR_SEVERE",
        name="Speed Restriction - Severe (30m on Throat)",
        description="Major caution order on MAS-BBQ throat increasing traversal time from 4m to 30m (7.5x).",
        group_type=ExperimentGroupType.SPEED_RESTRICTION,
        scenario_id="SCEN_31_3_TSR_SEVERE",
        scenario_name="MAS-BBQ Throat TSR 30m",
        scenario_description="Track speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN set to 30.0 minutes.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Travel time: 30.0 min (+26.0 min, 7.5x normal)",
        primary_target="MAS_BBQ_THROAT_SEGMENT_DOWN",
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 30.0},
    ),

    # -----------------------------------------------------------------------
    # 4. Blocked Track Section
    # -----------------------------------------------------------------------
    (DisruptionClass.BLOCKED_SECTION, SeverityLevel.MILD): SeverityExperimentSpec(
        disruption_class=DisruptionClass.BLOCKED_SECTION,
        severity_level=SeverityLevel.MILD,
        experiment_id="EXP_31_3_10_BLK_MILD",
        name="Blocked Section - Mild (Branch Line)",
        description="Temporary capacity block on isolated suburban branch line PAB_PTMS_SUBURBAN_DOWN.",
        group_type=ExperimentGroupType.BLOCKED_SECTION,
        scenario_id="SCEN_31_3_BLK_MILD",
        scenario_name="PAB-PTMS Branch Track Blockage",
        scenario_description="Track capacity set to 0 on branch section PAB_PTMS_SUBURBAN_DOWN.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Capacity: 0 on isolated branch section",
        primary_target="PAB_PTMS_SUBURBAN_DOWN",
        blocked_sections=["PAB_PTMS_SUBURBAN_DOWN"],
    ),
    (DisruptionClass.BLOCKED_SECTION, SeverityLevel.MODERATE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.BLOCKED_SECTION,
        severity_level=SeverityLevel.MODERATE,
        experiment_id="EXP_31_3_11_BLK_MOD",
        name="Blocked Section - Moderate (Bypass Line)",
        description="Temporary capacity block on secondary suburban bypass section RPM_MSB_SUBURBAN_BYPASS_DOWN.",
        group_type=ExperimentGroupType.BLOCKED_SECTION,
        scenario_id="SCEN_31_3_BLK_MOD",
        scenario_name="RPM-MSB Bypass Track Blockage",
        scenario_description="Track capacity set to 0 on secondary bypass section RPM_MSB_SUBURBAN_BYPASS_DOWN.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Capacity: 0 on secondary bypass section",
        primary_target="RPM_MSB_SUBURBAN_BYPASS_DOWN",
        blocked_sections=["RPM_MSB_SUBURBAN_BYPASS_DOWN"],
    ),
    (DisruptionClass.BLOCKED_SECTION, SeverityLevel.SEVERE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.BLOCKED_SECTION,
        severity_level=SeverityLevel.SEVERE,
        experiment_id="EXP_31_3_12_BLK_SEVERE",
        name="Blocked Section - Severe (Critical Mainline Throat)",
        description="Complete outage on critical bottleneck MAS_BBQ_THROAT_SEGMENT_DOWN (feasibility boundary condition).",
        group_type=ExperimentGroupType.BLOCKED_SECTION,
        scenario_id="SCEN_31_3_BLK_SEVERE",
        scenario_name="MAS-BBQ Throat Complete Blockage",
        scenario_description="Track capacity set to 0 on non-redundant throat MAS_BBQ_THROAT_SEGMENT_DOWN.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Capacity: 0 on non-redundant critical mainline throat",
        primary_target="MAS_BBQ_THROAT_SEGMENT_DOWN (feasibility cliff)",
        blocked_sections=["MAS_BBQ_THROAT_SEGMENT_DOWN"],
    ),

    # -----------------------------------------------------------------------
    # 5. Junction & Throat Contention
    # -----------------------------------------------------------------------
    (DisruptionClass.JUNCTION_CONTENTION, SeverityLevel.MILD): SeverityExperimentSpec(
        disruption_class=DisruptionClass.JUNCTION_CONTENTION,
        severity_level=SeverityLevel.MILD,
        experiment_id="EXP_31_3_13_JCT_MILD",
        name="Junction Contention - Mild (Capacity 3)",
        description="Relaxed interlocking constraint at Basin Bridge Junction (JCT_BBQ capacity 3).",
        group_type=ExperimentGroupType.JUNCTION_CONTENTION,
        scenario_id="SCEN_31_3_JCT_MILD",
        scenario_name="JCT_BBQ Capacity 3",
        scenario_description="Basin Bridge Junction capacity override set to 3.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Junction capacity: 3 at JCT_BBQ",
        primary_target="JCT_BBQ",
        junction_capacity_overrides={"JCT_BBQ": 3},
    ),
    (DisruptionClass.JUNCTION_CONTENTION, SeverityLevel.MODERATE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.JUNCTION_CONTENTION,
        severity_level=SeverityLevel.MODERATE,
        experiment_id="EXP_31_3_14_JCT_MOD",
        name="Junction Contention - Moderate (Capacity 2)",
        description="Restricted interlocking throughput at Basin Bridge Junction (JCT_BBQ capacity 2).",
        group_type=ExperimentGroupType.JUNCTION_CONTENTION,
        scenario_id="SCEN_31_3_JCT_MOD",
        scenario_name="JCT_BBQ Capacity 2",
        scenario_description="Basin Bridge Junction capacity override set to 2.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Junction capacity: 2 at JCT_BBQ",
        primary_target="JCT_BBQ",
        junction_capacity_overrides={"JCT_BBQ": 2},
    ),
    (DisruptionClass.JUNCTION_CONTENTION, SeverityLevel.SEVERE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.JUNCTION_CONTENTION,
        severity_level=SeverityLevel.SEVERE,
        experiment_id="EXP_31_3_15_JCT_SEVERE",
        name="Junction Contention - Severe (All Junctions Capacity 1)",
        description="Comprehensive single-clearance interlocking constriction across all key division junctions.",
        group_type=ExperimentGroupType.JUNCTION_CONTENTION,
        scenario_id="SCEN_31_3_JCT_SEVERE",
        scenario_name="Network-Wide Junction Throttling",
        scenario_description="Junction capacity override set to 1 for BBQ, PAB, MSB, and KOK.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Junction capacity: 1 at BBQ, PAB, MSB, KOK",
        primary_target="JCT_BBQ, JCT_PAB, JCT_MSB, JCT_KOK",
        junction_capacity_overrides={"JCT_BBQ": 1, "JCT_PAB": 1, "JCT_MSB": 1, "JCT_KOK": 1},
    ),

    # -----------------------------------------------------------------------
    # 6. Compound Multi-Disruption
    # -----------------------------------------------------------------------
    (DisruptionClass.COMPOUND_DISRUPTION, SeverityLevel.MILD): SeverityExperimentSpec(
        disruption_class=DisruptionClass.COMPOUND_DISRUPTION,
        severity_level=SeverityLevel.MILD,
        experiment_id="EXP_31_3_16_CMP_MILD",
        name="Compound Disruption - Mild",
        description="Combined mild perturbation: 5m departure delay on 12607 + 8m TSR on MAS-BBQ throat.",
        group_type=ExperimentGroupType.COMPOUND_DISRUPTION,
        scenario_id="SCEN_31_3_CMP_MILD",
        scenario_name="Mild Compound Disruption",
        scenario_description="5m departure delay + 8m throat TSR.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Dep delay: +5m; TSR: 8m on throat",
        primary_target="SRV_12607_01 & MAS_BBQ_THROAT_SEGMENT_DOWN",
        departure_delays={"SRV_12607_01": 5.0},
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0},
    ),
    (DisruptionClass.COMPOUND_DISRUPTION, SeverityLevel.MODERATE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.COMPOUND_DISRUPTION,
        severity_level=SeverityLevel.MODERATE,
        experiment_id="EXP_31_3_17_CMP_MOD",
        name="Compound Disruption - Moderate",
        description="Combined moderate disruption: 15m departure delay on 12607 + 15m TSR on throat + JCT_BBQ capacity 2.",
        group_type=ExperimentGroupType.COMPOUND_DISRUPTION,
        scenario_id="SCEN_31_3_CMP_MOD",
        scenario_name="Moderate Compound Disruption",
        scenario_description="15m departure delay + 15m throat TSR + JCT_BBQ capacity 2.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Dep delay: +15m; TSR: 15m; JCT_BBQ cap: 2",
        primary_target="SRV_12607_01, throat, JCT_BBQ",
        departure_delays={"SRV_12607_01": 15.0},
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 15.0},
        junction_capacity_overrides={"JCT_BBQ": 2},
    ),
    (DisruptionClass.COMPOUND_DISRUPTION, SeverityLevel.SEVERE): SeverityExperimentSpec(
        disruption_class=DisruptionClass.COMPOUND_DISRUPTION,
        severity_level=SeverityLevel.SEVERE,
        experiment_id="EXP_31_3_18_CMP_SEVERE",
        name="Compound Disruption - Severe",
        description="Multi-factor stress test: 30m departure delay + 30m TSR + JCT_BBQ cap 1 + 15m dwell extension at PER.",
        group_type=ExperimentGroupType.COMPOUND_DISRUPTION,
        scenario_id="SCEN_31_3_CMP_SEVERE",
        scenario_name="Severe Compound Disruption",
        scenario_description="30m departure delay + 30m throat TSR + JCT_BBQ cap 1 + 15m PER dwell extension.",
        time_horizon=(300.0, 1440.0),
        parameter_summary="Dep delay: +30m; TSR: 30m; JCT cap: 1; Dwell: +15m",
        primary_target="SRV_12607_01, throat, JCT_BBQ, PER station",
        departure_delays={"SRV_12607_01": 30.0},
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 30.0},
        junction_capacity_overrides={"JCT_BBQ": 1},
        station_delays={"SRV_12607_01": {"PER": 15.0}},
    ),
}


# ---------------------------------------------------------------------------
# Results Aggregation and Progression Analysis
# ---------------------------------------------------------------------------

@dataclass
class SeverityProgressionResult:
    """Aggregates comparative results across Mild -> Moderate -> Severe for a single disruption class."""
    disruption_class: DisruptionClass
    mild_result: ResearchExperimentResult
    moderate_result: ResearchExperimentResult
    severe_result: ResearchExperimentResult

    @property
    def baseline_delays(self) -> Tuple[float, float, float]:
        return (
            self.mild_result.metrics.feasible_baseline_total_delay_minutes,
            self.moderate_result.metrics.feasible_baseline_total_delay_minutes,
            self.severe_result.metrics.feasible_baseline_total_delay_minutes,
        )

    @property
    def optimized_delays(self) -> Tuple[float, float, float]:
        return (
            self.mild_result.metrics.optimized_total_delay_minutes,
            self.moderate_result.metrics.optimized_total_delay_minutes,
            self.severe_result.metrics.optimized_total_delay_minutes,
        )

    @property
    def delay_savings(self) -> Tuple[float, float, float]:
        return (
            self.mild_result.metrics.delay_savings_minutes,
            self.moderate_result.metrics.delay_savings_minutes,
            self.severe_result.metrics.delay_savings_minutes,
        )

    @property
    def solver_statuses(self) -> Tuple[str, str, str]:
        return (
            self.mild_result.metrics.solver_status,
            self.moderate_result.metrics.solver_status,
            self.severe_result.metrics.solver_status,
        )

    @property
    def solve_times(self) -> Tuple[float, float, float]:
        return (
            self.mild_result.metrics.solve_time_seconds,
            self.moderate_result.metrics.solve_time_seconds,
            self.severe_result.metrics.solve_time_seconds,
        )

    @property
    def is_monotonic_baseline(self) -> bool:
        """True if baseline delay increases or stays equal across mild <= mod <= sev."""
        m, d, s = self.baseline_delays
        return m <= d <= s

    @property
    def has_feasibility_cliff(self) -> bool:
        """True if severe level causes INFEASIBLE while mild/mod are OPTIMAL/FEASIBLE."""
        m_st, d_st, s_st = self.solver_statuses
        return m_st in ("OPTIMAL", "FEASIBLE") and d_st in ("OPTIMAL", "FEASIBLE") and s_st == "INFEASIBLE"


@dataclass
class SeveritySuiteResult:
    """Comprehensive aggregated results across all 18 severity experiments."""
    suite_id: str
    cohort: List[str]
    results: List[ResearchExperimentResult]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def progress_by_class(self) -> Dict[DisruptionClass, SeverityProgressionResult]:
        """Group results into 6 progression objects."""
        grouped: Dict[DisruptionClass, Dict[SeverityLevel, ResearchExperimentResult]] = {}
        for r in self.results:
            # Match experiment ID to spec
            for (d_cls, s_lvl), spec in SEVERITY_EXPERIMENT_SPECS.items():
                if spec.experiment_id == r.config.experiment_id:
                    grouped.setdefault(d_cls, {})[s_lvl] = r
                    break

        progressions: Dict[DisruptionClass, SeverityProgressionResult] = {}
        for d_cls, lvls in grouped.items():
            if SeverityLevel.MILD in lvls and SeverityLevel.MODERATE in lvls and SeverityLevel.SEVERE in lvls:
                progressions[d_cls] = SeverityProgressionResult(
                    disruption_class=d_cls,
                    mild_result=lvls[SeverityLevel.MILD],
                    moderate_result=lvls[SeverityLevel.MODERATE],
                    severe_result=lvls[SeverityLevel.SEVERE],
                )
        return progressions

    @property
    def feasibility_boundaries(self) -> List[Tuple[DisruptionClass, str]]:
        """Identify disruption classes that hit feasibility boundaries / cliffs."""
        boundaries: List[Tuple[DisruptionClass, str]] = []
        for d_cls, prog in self.progress_by_class.items():
            if prog.has_feasibility_cliff:
                boundaries.append((d_cls, "Severe outage triggers mathematical infeasibility cliff"))
        return boundaries

    @property
    def total_experiments(self) -> int:
        return len(self.results)

    @property
    def total_optimal(self) -> int:
        return sum(1 for r in self.results if r.metrics.solver_status == "OPTIMAL")

    @property
    def total_infeasible(self) -> int:
        return sum(1 for r in self.results if r.metrics.solver_status == "INFEASIBLE")

    def generate_markdown_table(self) -> str:
        """Generate a complete GitHub-flavored markdown table of all 18 experiments."""
        lines = [
            "| # | Disruption Class | Severity | Status | Thru | Baseline Delay (m) | CP-SAT Delay (m) | Savings (m) | Savings (%) | Conflicts | Solve Time (s) |",
            "|:---:|:---|:---:|:---:|:---:|---:|---:|---:|---:|:---:|---:|",
        ]
        for i, r in enumerate(self.results, 1):
            m = r.metrics
            # Find matching spec
            matched_spec: Optional[SeverityExperimentSpec] = None
            for spec in SEVERITY_EXPERIMENT_SPECS.values():
                if spec.experiment_id == r.config.experiment_id:
                    matched_spec = spec
                    break
            cls_name = matched_spec.disruption_class.value if matched_spec else r.config.group.value
            sev_name = matched_spec.severity_level.value if matched_spec else "-"

            thru_str = f"{m.throughput}/{len(self.cohort)}"
            sav_pct_str = f"{m.delay_savings_percent:+.1f}%" if m.solver_status != "INFEASIBLE" else "N/A"
            sav_min_str = f"{m.delay_savings_minutes:+.1f}" if m.solver_status != "INFEASIBLE" else "N/A"
            opt_delay_str = f"{m.optimized_total_delay_minutes:.1f}" if m.solver_status != "INFEASIBLE" else "N/A"
            conf_str = f"{m.initial_conflicts} -> {m.optimized_remaining_conflicts}"

            lines.append(
                f"| {i:2d} | {cls_name:<20} | {sev_name:<8} | {m.solver_status:<10} | {thru_str:<7} | {m.feasible_baseline_total_delay_minutes:18.1f} | {opt_delay_str:>16} | {sav_min_str:>11} | {sav_pct_str:>11} | {conf_str:<9} | {m.solve_time_seconds:14.3f} |"
            )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "cohort_size": len(self.cohort),
            "cohort_services": self.cohort,
            "timestamp": self.timestamp,
            "total_experiments": self.total_experiments,
            "optimal_count": self.total_optimal,
            "infeasible_count": self.total_infeasible,
            "feasibility_boundaries": [
                {"class": d_cls.value, "detail": detail}
                for d_cls, detail in self.feasibility_boundaries
            ],
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Suite Generation and Execution Functions
# ---------------------------------------------------------------------------

def create_severity_suite(
    cohort: Optional[List[str]] = None,
    time_limit_seconds: float = 15.0,
) -> List[ResearchExperimentConfig]:
    """Generates all 18 standardized severity experiment configs using the specified cohort."""
    target_cohort = list(cohort) if cohort is not None else list(COHORT_20)

    # Validate that no pending service is present
    intersection = set(target_cohort).intersection(PENDING_SERVICES)
    if intersection:
        raise ValueError(f"Cohort contains forbidden pending services: {intersection}")

    configs: List[ResearchExperimentConfig] = []
    # Order by disruption class, then severity: Mild -> Moderate -> Severe
    ordered_classes = [
        DisruptionClass.DEPARTURE_DELAY,
        DisruptionClass.DWELL_DELAY,
        DisruptionClass.SPEED_RESTRICTION,
        DisruptionClass.BLOCKED_SECTION,
        DisruptionClass.JUNCTION_CONTENTION,
        DisruptionClass.COMPOUND_DISRUPTION,
    ]
    ordered_severities = [
        SeverityLevel.MILD,
        SeverityLevel.MODERATE,
        SeverityLevel.SEVERE,
    ]

    for d_cls in ordered_classes:
        for s_lvl in ordered_severities:
            spec = SEVERITY_EXPERIMENT_SPECS.get((d_cls, s_lvl))
            if spec:
                cfg = spec.create_config(cohort=target_cohort, time_limit_seconds=time_limit_seconds)
                configs.append(cfg)

    return configs


def run_severity_experiments(
    network: Optional[Network] = None,
    cohort: Optional[List[str]] = None,
    time_limit_seconds: float = 15.0,
    suite_id: str = "PHASE_31_3_SEVERITY_SUITE",
) -> SeveritySuiteResult:
    """Executes the full 18-experiment severity suite and returns structured results."""
    target_cohort = list(cohort) if cohort is not None else list(COHORT_20)

    # Validate cohort
    intersection = set(target_cohort).intersection(PENDING_SERVICES)
    if intersection:
        raise ValueError(f"Cohort contains forbidden pending services: {intersection}")

    # Load network if not provided
    if network is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(repo_root, "data")
        net = Network()
        net.load_from_directory(os.path.join(data_dir, "infrastructure"))
        net.load_trains(os.path.join(data_dir, "trains", "train_identity", "trains.json"))
        net.load_services(os.path.join(data_dir, "trains", "service_definitions", "services.json"))
        net.load_timetable(os.path.join(data_dir, "trains", "published_timetables", "timetable.json"))
    else:
        net = network

    runner = ResearchExperimentRunner(network=net, time_limit_seconds=time_limit_seconds)
    configs = create_severity_suite(cohort=target_cohort, time_limit_seconds=time_limit_seconds)

    results: List[ResearchExperimentResult] = []
    for cfg in configs:
        res = runner.run_experiment(cfg)
        results.append(res)

    return SeveritySuiteResult(
        suite_id=suite_id,
        cohort=target_cohort,
        results=results,
    )
