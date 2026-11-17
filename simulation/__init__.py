# Network simulation module
from .network import (
    Network,
    Station, Platform, TrackSection, Junction, Route,
    Train, Service, TimetableEntry,
)
from .clock import SimulationClock, time_to_minutes, minutes_to_time_str
from .events import EventType, SimulationEvent, EventQueue
from .state import (
    TrainStatus,
    TrainRuntimeState,
    SimulationState,
    TrackSectionOccupancy,
    CapacityViolationError,
)
from .simulator import (
    TrainSimulator,
    find_track_section,
    SimulationError,
    MissingTrackSectionError,
    ServiceNotFoundError,
    InvalidRouteError,
)

from .conflicts import (
    Conflict,
    ConflictType,
    ConflictSeverity,
    ConflictDetector,
)
from .validation import (
    ValidationCheck,
    ValidationCategoryResult,
    DigitalTwinValidationReport,
    DigitalTwinValidator,
    run_digital_twin_validation,
)
from .cross_corridor import (
    CrossCorridorScenarioType,
    CorridorDataStatus,
    CorridorDataScope,
    CrossCorridorSimulationResult,
    CrossCorridorSuiteReport,
    CrossCorridorEvaluator,
    run_cross_corridor_evaluation,
)

__all__ = [
    'Network',
    'Station',
    'Platform',
    'TrackSection',
    'Junction',
    'Route',
    'Train',
    'Service',
    'TimetableEntry',
    'SimulationClock',
    'time_to_minutes',
    'minutes_to_time_str',
    'EventType',
    'SimulationEvent',
    'EventQueue',
    'TrainStatus',
    'TrainRuntimeState',
    'SimulationState',
    'TrackSectionOccupancy',
    'CapacityViolationError',
    'TrainSimulator',
    'find_track_section',
    'SimulationError',
    'MissingTrackSectionError',
    'ServiceNotFoundError',
    'InvalidRouteError',
    'Conflict',
    'ConflictType',
    'ConflictSeverity',
    'ConflictDetector',
    # Batch 16: Validation
    'ValidationCheck',
    'ValidationCategoryResult',
    'DigitalTwinValidationReport',
    'DigitalTwinValidator',
    'run_digital_twin_validation',
    # Batch 17: Cross-Corridor Simulation
    'CrossCorridorScenarioType',
    'CorridorDataStatus',
    'CorridorDataScope',
    'CrossCorridorSimulationResult',
    'CrossCorridorSuiteReport',
    'CrossCorridorEvaluator',
    'run_cross_corridor_evaluation',
]




