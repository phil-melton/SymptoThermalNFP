from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Iterable

from .taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixHeight,
    CervixOpening,
    FertilityState,
    FluidQuantity,
    FluidSensation,
    TemperatureUnit,
)

MAX_NOTES_LENGTH = 2000
_MENSES_START_LEVELS = {BleedingLevel.MEDIUM, BleedingLevel.HEAVY}


def parse_iso_date(value: str) -> date:
    """Parse ISO date values in YYYY-MM-DD format."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format.") from exc


def parse_hhmm_time(value: str) -> time:
    """Parse 24-hour HH:MM time values."""
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Time must use HH:MM format (24-hour).") from exc


@dataclass(slots=True)
class FluidObservation:
    sensation: FluidSensation
    quantity: FluidQuantity = FluidQuantity.NONE
    peak_quality: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "sensation": self.sensation.value,
            "quantity": self.quantity.value,
            "peak_quality": self.peak_quality,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FluidObservation":
        return cls(
            sensation=FluidSensation(value["sensation"]),
            quantity=FluidQuantity(value.get("quantity", FluidQuantity.NONE.value)),
            peak_quality=bool(value.get("peak_quality", False)),
        )


@dataclass(slots=True)
class CervicalPositionObservation:
    height: CervixHeight
    firmness: CervixFirmness
    opening: CervixOpening

    def as_dict(self) -> dict[str, Any]:
        return {
            "height": self.height.value,
            "firmness": self.firmness.value,
            "opening": self.opening.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CervicalPositionObservation":
        return cls(
            height=CervixHeight(value["height"]),
            firmness=CervixFirmness(value["firmness"]),
            opening=CervixOpening(value["opening"]),
        )


@dataclass(slots=True)
class DailyObservation:
    observation_date: date
    waking_temperature: float | None = None
    temperature_time: time | None = None
    temperature_disturbed: bool = False
    temperature_unit: TemperatureUnit | None = None
    fluid: FluidObservation | None = None
    cervical_position: CervicalPositionObservation | None = None
    bleeding: BleedingLevel = BleedingLevel.NONE
    notes: str = ""

    def __post_init__(self) -> None:
        if self.waking_temperature is None and self.temperature_time is not None:
            raise ValueError("Temperature time requires a temperature value.")
        if self.waking_temperature is not None and self.waking_temperature < 30:
            raise ValueError("Waking temperature looks invalid; expected realistic body temp.")
        if len(self.notes) > MAX_NOTES_LENGTH:
            raise ValueError(f"Notes exceed {MAX_NOTES_LENGTH} characters.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_date": self.observation_date.isoformat(),
            "waking_temperature": self.waking_temperature,
            "temperature_time": self.temperature_time.strftime("%H:%M") if self.temperature_time else None,
            "temperature_disturbed": self.temperature_disturbed,
            "temperature_unit": self.temperature_unit.value if self.temperature_unit else None,
            "fluid": self.fluid.as_dict() if self.fluid else None,
            "cervical_position": self.cervical_position.as_dict() if self.cervical_position else None,
            "bleeding": self.bleeding.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DailyObservation":
        fluid_data = value.get("fluid")
        cervix_data = value.get("cervical_position")
        tu = value.get("temperature_unit")
        return cls(
            observation_date=parse_iso_date(value["observation_date"]),
            waking_temperature=value.get("waking_temperature"),
            temperature_time=parse_hhmm_time(value["temperature_time"]) if value.get("temperature_time") else None,
            temperature_disturbed=bool(value.get("temperature_disturbed", False)),
            temperature_unit=TemperatureUnit(tu) if tu else None,
            fluid=FluidObservation.from_dict(fluid_data) if fluid_data else None,
            cervical_position=CervicalPositionObservation.from_dict(cervix_data) if cervix_data else None,
            bleeding=BleedingLevel(value.get("bleeding", BleedingLevel.NONE.value)),
            notes=value.get("notes", ""),
        )


@dataclass(slots=True)
class AppSettings:
    temperature_unit: TemperatureUnit = TemperatureUnit.CELSIUS
    default_wake_time: str = "06:30"
    track_cervical_position: bool = False

    def __post_init__(self) -> None:
        parse_hhmm_time(self.default_wake_time)

    def as_dict(self) -> dict[str, Any]:
        return {
            "temperature_unit": self.temperature_unit.value,
            "default_wake_time": self.default_wake_time,
            "track_cervical_position": self.track_cervical_position,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AppSettings":
        return cls(
            temperature_unit=TemperatureUnit(value.get("temperature_unit", TemperatureUnit.CELSIUS.value)),
            default_wake_time=value.get("default_wake_time", "06:30"),
            track_cervical_position=bool(value.get("track_cervical_position", False)),
        )


@dataclass(slots=True)
class CycleSnapshot:
    cycle_index: int
    start_date: date
    end_date: date
    span_days: int
    logged_days: int
    starts_with_menses: bool


@dataclass(slots=True)
class PriorCycleSummary:
    """Lightweight summary of a prior cycle, used for Doering rule."""
    cycle_length: int
    t_shift_day: int | None  # 1-indexed day of temperature shift
    confirmed_post_ov: bool  # did the cycle reach S2?


@dataclass(slots=True)
class DayRuleTrace:
    """Per-day trace showing which rules fired and why."""
    cycle_day: int  # 1-indexed
    observation_date: date
    state: FertilityState
    state_reason: str
    temp_celsius: float | None
    temp_valid: bool
    temp_disqualify_reason: str | None
    mucus_level: int | None  # ordinal quality level
    is_peak_day: bool
    rules_applied: list[str]


@dataclass(slots=True)
class EvaluationResult:
    """Full result of evaluating a cycle against Sensiplan rules."""
    states: list[FertilityState]
    day_traces: list[DayRuleTrace]
    t_shift_day: int | None  # 1-indexed cycle day of first high temp
    coverline_celsius: float | None
    peak_day: int | None  # 1-indexed cycle day
    temp_confirmed_day: int | None  # 1-indexed, evening of this day
    peak_confirmed_day: int | None  # 1-indexed, evening of this day
    infertile_from_day: int | None  # 1-indexed, first full S2 day
    disqualifiers: list[str]
    slow_rise_applied: bool
    drop_back_applied: bool


def build_cycle_history(observations: Iterable[DailyObservation]) -> list[CycleSnapshot]:
    """
    Group observations into cycle snapshots.

    This uses a conservative placeholder split strategy for Phase 1:
    a new cycle starts when medium/heavy bleeding appears after a day that did
    not have medium/heavy bleeding.
    """

    sorted_observations = sorted(observations, key=lambda item: item.observation_date)
    if not sorted_observations:
        return []

    cycles: list[CycleSnapshot] = []
    current_cycle: list[DailyObservation] = []
    previous: DailyObservation | None = None

    for observation in sorted_observations:
        new_cycle_start = (
            observation.bleeding in _MENSES_START_LEVELS
            and previous is not None
            and previous.bleeding not in _MENSES_START_LEVELS
        )

        if new_cycle_start and current_cycle:
            cycles.append(_make_cycle_snapshot(len(cycles) + 1, current_cycle))
            current_cycle = [observation]
        else:
            current_cycle.append(observation)

        previous = observation

    if current_cycle:
        cycles.append(_make_cycle_snapshot(len(cycles) + 1, current_cycle))

    return cycles


def _make_cycle_snapshot(cycle_index: int, cycle_days: list[DailyObservation]) -> CycleSnapshot:
    start = cycle_days[0].observation_date
    end = cycle_days[-1].observation_date
    span_days = (end - start).days + 1
    return CycleSnapshot(
        cycle_index=cycle_index,
        start_date=start,
        end_date=end,
        span_days=span_days,
        logged_days=len(cycle_days),
        starts_with_menses=cycle_days[0].bleeding in _MENSES_START_LEVELS,
    )
