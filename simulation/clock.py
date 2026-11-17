"""
simulation/clock.py
~~~~~~~~~~~~~~~~~~~
Deterministic simulation clock for railway traffic optimizer.

Provides time tracking, string conversion (HH:MM / HH:MM:SS), step-based
progression, and comparison operations. All internal times are represented
as minutes from midnight (0.0 = 00:00:00, 1439.0 = 23:59:00).
"""

from typing import Union, Optional


def time_to_minutes(time_val: Union[str, float, int]) -> float:
    """Convert 'HH:MM' or 'HH:MM:SS' string, or numeric minutes, to float minutes from midnight.

    Examples:
        time_to_minutes("05:30") -> 330.0
        time_to_minutes("05:30:30") -> 330.5
        time_to_minutes(330) -> 330.0
    """
    if isinstance(time_val, (int, float)):
        return float(time_val)

    if not isinstance(time_val, str):
        raise TypeError(f"Expected time string or number, got {type(time_val).__name__}")

    parts = time_val.strip().split(":")
    if len(parts) == 2:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = 0
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    else:
        raise ValueError(f"Invalid time format: '{time_val}'. Expected 'HH:MM' or 'HH:MM:SS'")

    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds < 60):
        raise ValueError(f"Time component out of range in '{time_val}'")

    return hours * 60.0 + minutes + (seconds / 60.0)


def minutes_to_time_str(minutes_val: float, include_seconds: bool = False) -> str:
    """Convert minutes from midnight to 'HH:MM' or 'HH:MM:SS' string.

    Examples:
        minutes_to_time_str(330.0) -> "05:30"
        minutes_to_time_str(330.5, include_seconds=True) -> "05:30:30"
    """
    # Normalize to 24-hour cycle (handles day rollover gracefully)
    total_seconds = int(round(minutes_val * 60)) % (24 * 3600)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if include_seconds:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}"


class SimulationClock:
    """Deterministic simulation clock.

    Tracks start time, current time, and elapsed duration in minutes.
    Supports fixed step increments and direct time jumps.
    """

    def __init__(
        self,
        start_time: Union[str, float, int] = "00:00",
        step_size_minutes: float = 1.0,
    ):
        if step_size_minutes <= 0:
            raise ValueError("step_size_minutes must be positive")

        self._start_minutes: float = time_to_minutes(start_time)
        self._current_minutes: float = self._start_minutes
        self._step_size: float = float(step_size_minutes)
        self._tick_count: int = 0

    @property
    def start_time(self) -> float:
        """Simulation start time in minutes from midnight."""
        return self._start_minutes

    @property
    def current_time(self) -> float:
        """Current simulation time in minutes from midnight."""
        return self._current_minutes

    @property
    def step_size(self) -> float:
        """Default step size in minutes."""
        return self._step_size

    @property
    def tick_count(self) -> int:
        """Number of ticks executed."""
        return self._tick_count

    @property
    def elapsed_minutes(self) -> float:
        """Total elapsed simulation time in minutes since start."""
        return self._current_minutes - self._start_minutes

    @property
    def current_time_str(self) -> str:
        """Current time formatted as 'HH:MM'."""
        return minutes_to_time_str(self._current_minutes, include_seconds=False)

    @property
    def current_time_str_full(self) -> str:
        """Current time formatted as 'HH:MM:SS'."""
        return minutes_to_time_str(self._current_minutes, include_seconds=True)

    def advance(self, delta_minutes: float) -> float:
        """Advance the clock by delta_minutes (must be >= 0). Returns new current time."""
        if delta_minutes < 0:
            raise ValueError("Cannot advance clock backwards in time")
        self._current_minutes += delta_minutes
        return self._current_minutes

    def advance_to(self, target_time: Union[str, float, int]) -> float:
        """Advance the clock directly to a target time. Target must be >= current_time."""
        target_minutes = time_to_minutes(target_time)
        if target_minutes < self._current_minutes:
            raise ValueError(
                f"Cannot advance to {target_minutes}m: target is earlier than current time {self._current_minutes}m"
            )
        self._current_minutes = target_minutes
        return self._current_minutes

    def tick(self) -> float:
        """Advance the clock by one step_size_minutes. Returns new current time."""
        self._current_minutes += self._step_size
        self._tick_count += 1
        return self._current_minutes

    def reset(self, new_start_time: Optional[Union[str, float, int]] = None):
        """Reset the clock back to start time (or a new start time)."""
        if new_start_time is not None:
            self._start_minutes = time_to_minutes(new_start_time)
        self._current_minutes = self._start_minutes
        self._tick_count = 0

    def __repr__(self) -> str:
        return (
            f"SimulationClock(current='{self.current_time_str}', "
            f"minutes={self._current_minutes:.2f}, elapsed={self.elapsed_minutes:.2f}m)"
        )
