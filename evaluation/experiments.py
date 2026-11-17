"""
evaluation/experiments.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Pre-configured, deterministic, research-grade experiment definitions.

Builds standardized operational experiments targeting real West Corridor services:
- SRV_12607_01 (Lalbagh SF Express, MAS -> SBC)
- SRV_12609_01 (Chennai-Mysuru SF Express, MAS -> MYS)
- SRV_12610_01 (Mysuru-Chennai SF Express, SBC -> MAS)
- SRV_43219_01 (Suburban EMU, MMC -> TRL)

All experiments operate exclusively on in-memory clones, ensuring zero JSON dataset mutation.
"""

from typing import List

from evaluation.models import ExperimentConfig
from optimization.scenarios import Scenario


def create_no_delay_baseline_experiment() -> ExperimentConfig:
    """Experiment 1: Nominal on-time operation across the West corridor."""
    scenario = Scenario(
        scenario_id="SCEN_EXP01_NO_DELAY",
        name="Nominal Unperturbed Baseline",
        description="All services dispatched precisely on published timetable with no external delays.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
        departure_delays={},
        station_delays={},
        track_speed_restrictions={},
    )
    return ExperimentConfig(
        experiment_id="EXP_01_NO_DELAY",
        name="Nominal Baseline Schedule",
        category="Baseline Validation",
        description="Evaluates CP-SAT vs Baseline under ideal conditions with zero injected delay.",
        scenario=scenario,
        time_limit_seconds=10.0,
    )


def create_single_train_delay_experiment() -> ExperimentConfig:
    """Experiment 2: Single train delayed departure on West Corridor SF Express 12607."""
    scenario = Scenario(
        scenario_id="SCEN_EXP02_SINGLE_DELAY",
        name="Single Train Origin Delay (12607 +15m)",
        description="Lalbagh SF Express (12607) experiences a 15-minute delayed departure at Chennai Central (MAS).",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
        departure_delays={"SRV_12607_01": 15.0},
        station_delays={},
        track_speed_restrictions={},
    )
    return ExperimentConfig(
        experiment_id="EXP_02_SINGLE_DELAY",
        name="Single Express Train Departure Delay",
        category="Primary Delay Perturbation",
        description="Assesses how a 15m departure delay on a premier Superfast train propagates and is resolved.",
        scenario=scenario,
        time_limit_seconds=10.0,
    )


def create_multiple_simultaneous_delays_experiment() -> ExperimentConfig:
    """Experiment 3: Simultaneous delays on multiple outbound services competing for throat tracks."""
    scenario = Scenario(
        scenario_id="SCEN_EXP03_MULTI_DELAY",
        name="Multiple Simultaneous Delays (12607 +20m, 12609 +10m)",
        description="Simultaneous departure delays on 12607 (+20m) and 12609 (+10m) with 5m extra dwell at Perambur.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
        departure_delays={"SRV_12607_01": 20.0, "SRV_12609_01": 10.0},
        station_delays={"SRV_12607_01": {"PER": 5.0}},
        track_speed_restrictions={},
    )
    return ExperimentConfig(
        experiment_id="EXP_03_MULTI_DELAY",
        name="Simultaneous Multi-Train Delays",
        category="Compound Disruption",
        description="Tests resolution of conflicting slot requests when multiple outbound trains are delayed simultaneously.",
        scenario=scenario,
        time_limit_seconds=15.0,
    )


def create_speed_restriction_experiment() -> ExperimentConfig:
    """Experiment 4: Temporary Speed Restriction (TSR) on Chennai-Basin Bridge throat corridor."""
    scenario = Scenario(
        scenario_id="SCEN_EXP04_TSR",
        name="Throat Track Speed Restriction (MAS-BBQ)",
        description="Speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN increases traversal time from standard ~2m to 6m.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
        departure_delays={},
        station_delays={},
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 6.0},
    )
    return ExperimentConfig(
        experiment_id="EXP_04_SPEED_RESTRICTION",
        name="Throat Speed Restriction (TSR)",
        category="Infrastructure Constraint",
        description="Evaluates throughput and delay propagation when throat track traversal time triples.",
        scenario=scenario,
        time_limit_seconds=15.0,
    )


def create_junction_bottleneck_experiment() -> ExperimentConfig:
    """Experiment 5: Junction capacity constraint & headway tightening at Basin Bridge Junction (J_BBQ)."""
    scenario = Scenario(
        scenario_id="SCEN_EXP05_JUNCTION_BOTTLENECK",
        name="Junction Capacity Bottleneck (J_BBQ)",
        description="Junction capacity at J_BBQ constrained to 1 concurrent move with tightened 5m headway on throat segments.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
        departure_delays={"SRV_12607_01": 5.0, "SRV_12609_01": 5.0},
        station_delays={},
        junction_capacity_overrides={"J_BBQ": 1},
        custom_headway_overrides={"MAS_BBQ_THROAT_SEGMENT_DOWN": 5.0},
    )
    return ExperimentConfig(
        experiment_id="EXP_05_JUNCTION_BOTTLENECK",
        name="Junction Bottleneck & Headway Tightening",
        category="Bottleneck Contention",
        description="Tests precedence ordering and headway spacing when junction capacity is restricted.",
        scenario=scenario,
        time_limit_seconds=15.0,
    )


def create_severe_compound_experiment() -> ExperimentConfig:
    """Experiment 6: Severe compound disruption with multiple delays + TSR."""
    scenario = Scenario(
        scenario_id="SCEN_EXP06_SEVERE_COMPOUND",
        name="Severe Compound Disruption (12607 +30m, 12609 +20m, 43219 +10m, Throat TSR)",
        description=(
            "Severe compound disruption: 12607 +30m, 12609 +20m, 43219 +10m departure delays, "
            "plus throat-track speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN (6m traversal)."
        ),
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
        departure_delays={"SRV_12607_01": 30.0, "SRV_12609_01": 20.0, "SRV_43219_01": 10.0},
        station_delays={},
        track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 6.0},
    )
    return ExperimentConfig(
        experiment_id="EXP_06_SEVERE_COMPOUND",
        name="Severe Compound Multi-Train Disruption",
        category="Extreme Multi-Disruption",
        description="Assesses CP-SAT resolution under simultaneous heavy origin delays and throat infrastructure capacity reduction.",
        scenario=scenario,
        time_limit_seconds=15.0,
    )


def create_standard_evaluation_suite() -> List[ExperimentConfig]:
    """Returns the complete set of 5 standard benchmark experiments."""
    return [
        create_no_delay_baseline_experiment(),
        create_single_train_delay_experiment(),
        create_multiple_simultaneous_delays_experiment(),
        create_speed_restriction_experiment(),
        create_junction_bottleneck_experiment(),
    ]


def create_consolidated_benchmark_suite() -> List[ExperimentConfig]:
    """Returns all 6 core operational benchmark experiments including severe compound disruption."""
    return [
        create_no_delay_baseline_experiment(),
        create_single_train_delay_experiment(),
        create_multiple_simultaneous_delays_experiment(),
        create_speed_restriction_experiment(),
        create_junction_bottleneck_experiment(),
        create_severe_compound_experiment(),
    ]

