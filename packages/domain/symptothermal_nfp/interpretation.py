from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any, Iterable

from .models import (
    AppSettings,
    CervicalPositionObservation,
    CycleSnapshot,
    DailyObservation,
    FluidObservation,
)
from .taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixOpening,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    RuleContext,
    TemperatureUnit,
    TrackingGoal,
)

RULE_PACK_VERSION = "stm-v1"
BBT_THRESHOLD_C = 0.2
_TEMP_COMPARISON_EPSILON_C = 1e-9
_MENSES_START_LEVELS = {BleedingLevel.MEDIUM, BleedingLevel.HEAVY}
_TRANSITION_CONTEXTS = {
    RuleContext.POST_HORMONAL,
    RuleContext.POSTPARTUM,
    RuleContext.POST_MISCARRIAGE,
}
_ALWAYS_LOCKED_PHASE1_CONTEXTS = {RuleContext.PERIMENOPAUSE}


class FertilityStatus(str, Enum):
    RELATIVE_INFERTILITY = "relative_infertility"
    POTENTIALLY_FERTILE = "potentially_fertile"
    ABSOLUTE_INFERTILITY_FROM_EVENING = "absolute_infertility_from_evening"
    ABSOLUTE_INFERTILITY = "absolute_infertility"
    BASIC_INFERTILE_PATTERN_ALTERNATE_EVENING = "basic_infertile_pattern_alternate_evening"


class CyclePhase(str, Enum):
    PHASE_1 = "phase_1"
    FERTILE_WINDOW = "fertile_window"
    PHASE_3 = "phase_3"
    BASIC_INFERTILE_PATTERN = "basic_infertile_pattern"


class WarningSeverity(str, Enum):
    INFO = "info"
    CAUTION = "caution"
    BLOCKING = "blocking"


class UserFertilityLabel(str, Enum):
    FERTILITY_POSSIBLE = "fertility_possible"
    POST_OVULATION_CONFIRMED = "post_ovulation_confirmed"
    LOWER_PROBABILITY_METHOD_RULES_APPLY = "lower_probability_method_rules_apply"
    NOT_ENOUGH_INFORMATION = "not_enough_information"


@dataclass(slots=True)
class RuleTrace:
    code: str
    message: str
    observation_date: date | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "observation_date": _date_or_none(self.observation_date),
        }


@dataclass(slots=True)
class InterpretationWarning:
    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.CAUTION
    observation_date: date | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "observation_date": _date_or_none(self.observation_date),
        }


@dataclass(slots=True)
class TemperatureShift:
    first_high_date: date
    confirmed_date: date
    coverline_celsius: float
    baseline_dates: list[date]
    high_dates: list[date]
    threshold_met_on_third: bool
    fourth_day_exception: bool = False
    unclear_mucus_exception: bool = False
    premature_rise_ignored: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "first_high_date": self.first_high_date.isoformat(),
            "confirmed_date": self.confirmed_date.isoformat(),
            "coverline_celsius": round(self.coverline_celsius, 3),
            "baseline_dates": [item.isoformat() for item in self.baseline_dates],
            "high_dates": [item.isoformat() for item in self.high_dates],
            "threshold_met_on_third": self.threshold_met_on_third,
            "fourth_day_exception": self.fourth_day_exception,
            "unclear_mucus_exception": self.unclear_mucus_exception,
            "premature_rise_ignored": self.premature_rise_ignored,
        }


@dataclass(slots=True)
class InterpretationProgress:
    temperature_high_count: int
    temperature_high_required: int
    temperature_confirmed: bool
    mucus_lower_quality_count: int
    mucus_lower_quality_required: int
    mucus_confirmed: bool
    temperature_recorded_today: bool
    mucus_recorded_today: bool
    data_quality_messages: list[str] = field(default_factory=list)
    next_step: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "temperature_high_count": self.temperature_high_count,
            "temperature_high_required": self.temperature_high_required,
            "temperature_confirmed": self.temperature_confirmed,
            "mucus_lower_quality_count": self.mucus_lower_quality_count,
            "mucus_lower_quality_required": self.mucus_lower_quality_required,
            "mucus_confirmed": self.mucus_confirmed,
            "temperature_recorded_today": self.temperature_recorded_today,
            "mucus_recorded_today": self.mucus_recorded_today,
            "data_quality_messages": list(self.data_quality_messages),
            "next_step": self.next_step,
        }


@dataclass(slots=True)
class UserFeedback:
    label: UserFertilityLabel
    headline: str
    summary: str
    action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "headline": self.headline,
            "summary": self.summary,
            "action": self.action,
        }


@dataclass(slots=True)
class DailyInterpretation:
    observation_date: date
    cycle_day: int
    status: FertilityStatus
    phase: CyclePhase
    reasons: list[str] = field(default_factory=list)
    progress: InterpretationProgress | None = None
    feedback: UserFeedback | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_date": self.observation_date.isoformat(),
            "cycle_day": self.cycle_day,
            "status": self.status.value,
            "phase": self.phase.value,
            "reasons": list(self.reasons),
            "progress": self.progress.as_dict() if self.progress else None,
            "feedback": self.feedback.as_dict() if self.feedback else None,
        }


@dataclass(slots=True)
class CycleInterpretation:
    cycle_index: int
    start_date: date
    end_date: date
    span_days: int
    logged_days: int
    starts_with_menses: bool
    phase1_end_date: date | None
    fertile_window_start_date: date
    peak_day: date | None
    mucus_confirmation_date: date | None
    temperature_shift: TemperatureShift | None
    absolute_infertility_start_date: date | None
    luteal_phase_days: int | None
    warnings: list[InterpretationWarning] = field(default_factory=list)
    traces: list[RuleTrace] = field(default_factory=list)
    days: list[DailyInterpretation] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle_index": self.cycle_index,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "span_days": self.span_days,
            "logged_days": self.logged_days,
            "starts_with_menses": self.starts_with_menses,
            "phase1_end_date": _date_or_none(self.phase1_end_date),
            "fertile_window_start_date": self.fertile_window_start_date.isoformat(),
            "peak_day": _date_or_none(self.peak_day),
            "mucus_confirmation_date": _date_or_none(self.mucus_confirmation_date),
            "temperature_shift": self.temperature_shift.as_dict() if self.temperature_shift else None,
            "absolute_infertility_start_date": _date_or_none(self.absolute_infertility_start_date),
            "luteal_phase_days": self.luteal_phase_days,
            "warnings": [item.as_dict() for item in self.warnings],
            "traces": [item.as_dict() for item in self.traces],
            "days": [item.as_dict() for item in self.days],
        }


@dataclass(slots=True)
class InterpretationReport:
    rule_pack_version: str
    generated_at: str
    settings: dict[str, Any]
    cycles: list[CycleInterpretation]
    warnings: list[InterpretationWarning] = field(default_factory=list)
    traces: list[RuleTrace] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_pack_version": self.rule_pack_version,
            "generated_at": self.generated_at,
            "settings": dict(self.settings),
            "warnings": [item.as_dict() for item in self.warnings],
            "traces": [item.as_dict() for item in self.traces],
            "cycles": [item.as_dict() for item in self.cycles],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent, sort_keys=True)


def evaluate_observations(
    observations: Iterable[DailyObservation],
    settings: AppSettings | None = None,
) -> InterpretationReport:
    """Evaluate observations with a conservative symptothermal rule pack."""

    active_settings = settings or AppSettings()
    sorted_observations = sorted(observations, key=lambda item: item.observation_date)
    report_warnings: list[InterpretationWarning] = []
    report_traces: list[RuleTrace] = []

    if not sorted_observations:
        return InterpretationReport(
            rule_pack_version=RULE_PACK_VERSION,
            generated_at=_utc_now_iso(),
            settings=active_settings.as_dict(),
            cycles=[],
            warnings=[
                InterpretationWarning(
                    code="no_observations",
                    message="No observations are available for interpretation.",
                    severity=WarningSeverity.INFO,
                )
            ],
        )

    if active_settings.rule_context in _TRANSITION_CONTEXTS and active_settings.transition_cycle_count < 6:
        report_warnings.append(
            InterpretationWarning(
                code="transition_context_phase1_locked",
                message=(
                    "Pre-ovulatory relative infertility is locked during the first "
                    "six transition cycles."
                ),
                severity=WarningSeverity.BLOCKING,
            )
        )

    if active_settings.rule_context in _ALWAYS_LOCKED_PHASE1_CONTEXTS:
        report_warnings.append(
            InterpretationWarning(
                code="special_context_phase1_locked",
                message=(
                    "Pre-ovulatory relative infertility is not calculated in this "
                    "special context; use method-specific instruction."
                ),
                severity=WarningSeverity.BLOCKING,
            )
        )

    if not any(item.fluid for item in sorted_observations):
        report_warnings.append(
            InterpretationWarning(
                code="bbt_without_mucus",
                message=(
                    "No mucus observations were found; BBT alone can confirm only that "
                    "ovulation may already have occurred."
                ),
            )
        )

    cycle_days = _build_interpretation_cycles(sorted_observations, active_settings)
    cycles: list[CycleInterpretation] = []
    previous_lengths: list[int] = []
    previous_temperature_rise_days: list[int] = []

    for index, days in enumerate(cycle_days, start=1):
        cycle = _evaluate_cycle(
            days=days,
            cycle_index=index,
            settings=active_settings,
            previous_cycle_lengths=previous_lengths,
            previous_temperature_rise_days=previous_temperature_rise_days,
        )
        cycles.append(cycle)
        previous_lengths.append(cycle.span_days)
        if cycle.temperature_shift:
            previous_temperature_rise_days.append(
                (cycle.temperature_shift.first_high_date - cycle.start_date).days + 1
            )

    _apply_luteal_phase_warnings(cycles)

    return InterpretationReport(
        rule_pack_version=RULE_PACK_VERSION,
        generated_at=_utc_now_iso(),
        settings=active_settings.as_dict(),
        cycles=cycles,
        warnings=report_warnings,
        traces=report_traces,
    )


def _evaluate_cycle(
    *,
    days: list[DailyObservation],
    cycle_index: int,
    settings: AppSettings,
    previous_cycle_lengths: list[int],
    previous_temperature_rise_days: list[int],
) -> CycleInterpretation:
    start = days[0].observation_date
    end = days[-1].observation_date
    span_days = (end - start).days + 1
    warnings: list[InterpretationWarning] = []
    traces: list[RuleTrace] = []

    peak_day = _find_peak_day(days)
    mucus_confirmation_date = _find_mucus_confirmation_date(days, peak_day)
    temperature_shift = _find_temperature_shift(
        days,
        settings,
        peak_day=peak_day,
        require_fourth_for_unclear_mucus=peak_day is None,
    )

    if temperature_shift and peak_day is None:
        warnings.append(
            InterpretationWarning(
                code="unclear_mucus_peak",
                message=(
                    "A temperature shift was detected without a locked Peak Day; "
                    "the fourth elevated temperature rule was required."
                ),
            )
        )
        traces.append(
            RuleTrace(
                code="temperature_unclear_mucus_exception",
                message="Temperature confirmation used the unclear mucus exception.",
                observation_date=temperature_shift.confirmed_date,
            )
        )

    if temperature_shift and temperature_shift.premature_rise_ignored:
        traces.append(
            RuleTrace(
                code="premature_temperature_rise_ignored",
                message="A pre-Peak temperature rise was ignored; highs were counted after Peak Day.",
                observation_date=peak_day,
            )
        )

    for observation in days:
        temp_c = _temperature_celsius(observation, settings, include_disturbed=True)
        if temp_c is not None and temp_c >= 38.0:
            warnings.append(
                InterpretationWarning(
                    code="elevated_temperature",
                    message="Elevated temperature can make BBT interpretation unreliable.",
                    observation_date=observation.observation_date,
                )
            )

    if _has_internal_menses_start(days) and temperature_shift is None:
        warnings.append(
            InterpretationWarning(
                code="possible_anovulatory_bleeding",
                message=(
                    "Bleeding appeared before an ovulatory temperature shift was confirmed; "
                    "it is treated as possible breakthrough bleeding."
                ),
            )
        )

    fertile_window_start_date, phase1_end_date = _phase1_dates(
        days=days,
        settings=settings,
        previous_cycle_lengths=previous_cycle_lengths,
        previous_temperature_rise_days=previous_temperature_rise_days,
        traces=traces,
        warnings=warnings,
    )

    absolute_start = None
    if mucus_confirmation_date and temperature_shift:
        absolute_start = max(mucus_confirmation_date, temperature_shift.confirmed_date)

    bip_statuses = _bip_statuses(days, settings)
    daily = _daily_interpretations(
        days=days,
        fertile_window_start_date=fertile_window_start_date,
        absolute_start_date=absolute_start,
        bip_statuses=bip_statuses,
        settings=settings,
    )

    if temperature_shift:
        traces.append(
            RuleTrace(
                code="temperature_shift_confirmed",
                message=(
                    "Temperature shift confirmed with coverline "
                    f"{temperature_shift.coverline_celsius:.2f} C."
                ),
                observation_date=temperature_shift.confirmed_date,
            )
        )

    if mucus_confirmation_date:
        traces.append(
            RuleTrace(
                code="mucus_countdown_confirmed",
                message="Three lower-quality or dry observations followed Peak Day.",
                observation_date=mucus_confirmation_date,
            )
        )

    if absolute_start:
        traces.append(
            RuleTrace(
                code="double_check_confirmed",
                message="Post-ovulatory infertility begins on the evening of the later confirmation.",
                observation_date=absolute_start,
            )
        )

    return CycleInterpretation(
        cycle_index=cycle_index,
        start_date=start,
        end_date=end,
        span_days=span_days,
        logged_days=len(days),
        starts_with_menses=days[0].bleeding in _MENSES_START_LEVELS,
        phase1_end_date=phase1_end_date,
        fertile_window_start_date=fertile_window_start_date,
        peak_day=peak_day,
        mucus_confirmation_date=mucus_confirmation_date,
        temperature_shift=temperature_shift,
        absolute_infertility_start_date=absolute_start,
        luteal_phase_days=None,
        warnings=warnings,
        traces=traces,
        days=daily,
    )


def _phase1_dates(
    *,
    days: list[DailyObservation],
    settings: AppSettings,
    previous_cycle_lengths: list[int],
    previous_temperature_rise_days: list[int],
    traces: list[RuleTrace],
    warnings: list[InterpretationWarning],
) -> tuple[date, date | None]:
    start = days[0].observation_date

    if settings.rule_context in _TRANSITION_CONTEXTS and settings.transition_cycle_count < 6:
        traces.append(
            RuleTrace(
                code="phase1_locked_transition_context",
                message="Transition context locks Phase 1 relative infertility.",
                observation_date=start,
            )
        )
        return start, None

    if settings.rule_context in _ALWAYS_LOCKED_PHASE1_CONTEXTS:
        traces.append(
            RuleTrace(
                code="phase1_locked_special_context",
                message="Special context locks Phase 1 relative infertility.",
                observation_date=start,
            )
        )
        return start, None

    calendar_start = _calendar_fertile_start(
        start=start,
        previous_cycle_lengths=previous_cycle_lengths,
        previous_temperature_rise_days=previous_temperature_rise_days,
        settings=settings,
        traces=traces,
    )
    physical_start = _physical_fertile_start(days, settings)

    fertile_start = _min_date(calendar_start, physical_start) or start
    phase1_end = fertile_start - timedelta(days=1) if fertile_start > start else None

    if calendar_start == start and len(previous_cycle_lengths) < 4:
        warnings.append(
            InterpretationWarning(
                code="insufficient_cycle_history",
                message="Fewer than four prior cycles are available; Phase 1 is treated as fertile.",
                observation_date=start,
            )
        )

    if physical_start:
        traces.append(
            RuleTrace(
                code="physical_phase1_override",
                message="Mucus or cervix signs ended Phase 1 immediately.",
                observation_date=physical_start,
            )
        )

    return fertile_start, phase1_end


def _calendar_fertile_start(
    *,
    start: date,
    previous_cycle_lengths: list[int],
    previous_temperature_rise_days: list[int],
    settings: AppSettings,
    traces: list[RuleTrace],
) -> date:
    history_count = len(previous_cycle_lengths)
    if history_count < 4:
        traces.append(
            RuleTrace(
                code="calendar_no_phase1_history",
                message="0-3 prior cycles logged; no pre-ovulatory relative infertility is calculated.",
                observation_date=start,
            )
        )
        return start

    shortest = min(previous_cycle_lengths)
    if history_count <= 6:
        last_relative_day = min(max(shortest - 21, 0), 5)
        rule_code = "calendar_s21_first5"
    elif history_count <= 12:
        last_relative_day = max(shortest - 21, 0)
        rule_code = "calendar_s21"
    else:
        last_relative_day = max(shortest - 20, 0)
        rule_code = "calendar_s20"

    if settings.use_doering_rule and history_count >= 12 and previous_temperature_rise_days:
        earliest_rise = min(previous_temperature_rise_days)
        doering_day = earliest_rise - (7 if earliest_rise >= 14 else 6)
        doering_day = max(doering_day, 0)
        if doering_day < last_relative_day:
            last_relative_day = doering_day
            rule_code = "calendar_doering"

    if settings.use_rotzer_rule and previous_cycle_lengths and all(item >= 26 for item in previous_cycle_lengths):
        if last_relative_day < 6:
            last_relative_day = 6
            rule_code = "calendar_rotzer"

    traces.append(
        RuleTrace(
            code=rule_code,
            message=f"Calendar rule allows relative infertility through cycle day {last_relative_day}.",
            observation_date=start,
        )
    )
    return start + timedelta(days=last_relative_day)


def _physical_fertile_start(days: list[DailyObservation], settings: AppSettings) -> date | None:
    for observation in days:
        if _has_phase1_mucus_override(observation.fluid):
            return observation.observation_date
        if settings.track_cervical_position and _has_cervix_override(observation.cervical_position):
            return observation.observation_date
    return None


def _has_phase1_mucus_override(fluid: FluidObservation | None) -> bool:
    if fluid is None:
        return False
    if fluid.sensation != FluidSensation.DRY:
        return True
    if fluid.quantity != FluidQuantity.NONE:
        return True
    if fluid.color != MucusColor.NONE:
        return True
    if fluid.texture != MucusTexture.NONE:
        return True
    return fluid.amount is not None or fluid.peak_quality


def _has_cervix_override(cervix: CervicalPositionObservation | None) -> bool:
    if cervix is None:
        return False
    return cervix.firmness != CervixFirmness.FIRM or cervix.opening != CervixOpening.CLOSED


def _find_peak_day(days: list[DailyObservation]) -> date | None:
    last_peak_index: int | None = None
    for index, observation in enumerate(days):
        if _is_peak_quality_mucus(observation.fluid):
            last_peak_index = index

    if last_peak_index is None:
        return None

    for later in days[last_peak_index + 1 :]:
        if _is_lower_quality_or_dry(later.fluid):
            return days[last_peak_index].observation_date
    return None


def _find_mucus_confirmation_date(days: list[DailyObservation], peak_day: date | None) -> date | None:
    if peak_day is None:
        return None

    expected_date = peak_day + timedelta(days=1)
    count = 0
    for observation in days:
        if observation.observation_date <= peak_day:
            continue
        if observation.observation_date != expected_date:
            return None
        expected_date += timedelta(days=1)
        if observation.fluid is None:
            return None
        if _is_lower_quality_or_dry(observation.fluid):
            count += 1
            if count == 3:
                return observation.observation_date
        else:
            count = 0
    return None


def _is_peak_quality_mucus(fluid: FluidObservation | None) -> bool:
    if fluid is None:
        return False
    return (
        fluid.peak_quality
        or fluid.sensation in {FluidSensation.WATERY, FluidSensation.SLIPPERY}
        or fluid.color == MucusColor.CLEAR
        or fluid.texture in {MucusTexture.STRETCHY, MucusTexture.SLIPPERY}
    )


def _is_lower_quality_or_dry(fluid: FluidObservation | None) -> bool:
    if fluid is None:
        return False
    if _is_peak_quality_mucus(fluid):
        return False
    if fluid.sensation in {FluidSensation.DRY, FluidSensation.STICKY, FluidSensation.CREAMY}:
        return True
    if fluid.color in {MucusColor.CLOUDY, MucusColor.WHITE, MucusColor.YELLOW}:
        return fluid.texture not in {MucusTexture.STRETCHY, MucusTexture.SLIPPERY}
    return fluid.texture in {
        MucusTexture.NONE,
        MucusTexture.STICKY,
        MucusTexture.TACKY,
        MucusTexture.CRUMBLY,
        MucusTexture.CREAMY,
    }


def _find_temperature_shift(
    days: list[DailyObservation],
    settings: AppSettings,
    *,
    peak_day: date | None,
    require_fourth_for_unclear_mucus: bool,
) -> TemperatureShift | None:
    premature_shift = None
    if peak_day:
        premature_shift = _scan_temperature_shift(
            days,
            settings,
            earliest_first_high_date=None,
            latest_first_high_date=peak_day,
            require_fourth=False,
        )

    shift = _scan_temperature_shift(
        days,
        settings,
        earliest_first_high_date=peak_day + timedelta(days=1) if peak_day else None,
        latest_first_high_date=None,
        require_fourth=require_fourth_for_unclear_mucus,
    )
    if shift and premature_shift:
        shift.premature_rise_ignored = True
    return shift


def _scan_temperature_shift(
    days: list[DailyObservation],
    settings: AppSettings,
    *,
    earliest_first_high_date: date | None,
    latest_first_high_date: date | None,
    require_fourth: bool,
) -> TemperatureShift | None:
    temps = [_temperature_celsius(observation, settings) for observation in days]

    for high_start in range(6, len(days)):
        high_start_date = days[high_start].observation_date
        if earliest_first_high_date and high_start_date < earliest_first_high_date:
            continue
        if latest_first_high_date and high_start_date > latest_first_high_date:
            continue

        if not _dates_are_consecutive(days, high_start - 6, 9):
            continue

        baseline = temps[high_start - 6 : high_start]
        highs = temps[high_start : high_start + 3]
        if len(highs) < 3 or any(item is None for item in baseline + highs):
            continue

        coverline = max(item for item in baseline if item is not None)
        high_values = [item for item in highs if item is not None]
        if not all(item > coverline for item in high_values):
            continue

        third_meets_threshold = _meets_temperature_threshold(high_values[2], coverline)
        needs_fourth = require_fourth or not third_meets_threshold

        high_dates = [days[high_start + offset].observation_date for offset in range(3)]
        confirmed_index = high_start + 2
        fourth_day_exception = False
        unclear_mucus_exception = require_fourth

        if needs_fourth:
            fourth_index = high_start + 3
            if fourth_index >= len(days):
                continue
            if not _dates_are_consecutive(days, high_start, 4):
                continue
            fourth_temp = temps[fourth_index]
            if fourth_temp is None or fourth_temp <= coverline:
                continue
            high_dates.append(days[fourth_index].observation_date)
            confirmed_index = fourth_index
            fourth_day_exception = not third_meets_threshold

        return TemperatureShift(
            first_high_date=days[high_start].observation_date,
            confirmed_date=days[confirmed_index].observation_date,
            coverline_celsius=coverline,
            baseline_dates=[days[index].observation_date for index in range(high_start - 6, high_start)],
            high_dates=high_dates,
            threshold_met_on_third=third_meets_threshold,
            fourth_day_exception=fourth_day_exception,
            unclear_mucus_exception=unclear_mucus_exception,
        )

    return None


def _temperature_celsius(
    observation: DailyObservation,
    settings: AppSettings,
    *,
    include_disturbed: bool = False,
) -> float | None:
    if observation.waking_temperature is None:
        return None
    if observation.temperature_disturbed and not include_disturbed:
        return None
    unit = observation.temperature_unit or settings.temperature_unit
    if unit == TemperatureUnit.FAHRENHEIT:
        return (observation.waking_temperature - 32.0) * 5.0 / 9.0
    return observation.waking_temperature


def _meets_temperature_threshold(value: float, coverline: float) -> bool:
    return value + _TEMP_COMPARISON_EPSILON_C >= coverline + BBT_THRESHOLD_C


def _dates_are_consecutive(days: list[DailyObservation], start_index: int, length: int) -> bool:
    if start_index < 0 or start_index + length > len(days):
        return False
    for index in range(start_index + 1, start_index + length):
        if days[index].observation_date != days[index - 1].observation_date + timedelta(days=1):
            return False
    return True


def _daily_interpretations(
    *,
    days: list[DailyObservation],
    fertile_window_start_date: date,
    absolute_start_date: date | None,
    bip_statuses: dict[date, FertilityStatus],
    settings: AppSettings,
) -> list[DailyInterpretation]:
    start = days[0].observation_date
    daily: list[DailyInterpretation] = []

    for index, observation in enumerate(days):
        observation_date = observation.observation_date
        cycle_day = (observation_date - start).days + 1
        reasons: list[str] = []

        if absolute_start_date and observation_date > absolute_start_date:
            status = FertilityStatus.ABSOLUTE_INFERTILITY
            phase = CyclePhase.PHASE_3
            reasons.append("Post-ovulatory double-check already confirmed.")
        elif absolute_start_date and observation_date == absolute_start_date:
            status = FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING
            phase = CyclePhase.PHASE_3
            reasons.append("Post-ovulatory double-check begins this evening.")
        elif observation_date < fertile_window_start_date:
            status = FertilityStatus.RELATIVE_INFERTILITY
            phase = CyclePhase.PHASE_1
            reasons.append("Within conservative pre-ovulatory relative infertility.")
        else:
            status = FertilityStatus.POTENTIALLY_FERTILE
            phase = CyclePhase.FERTILE_WINDOW
            reasons.append("Post-ovulatory double-check is not yet confirmed.")

        if (
            status == FertilityStatus.POTENTIALLY_FERTILE
            and observation_date in bip_statuses
        ):
            status = bip_statuses[observation_date]
            phase = CyclePhase.BASIC_INFERTILE_PATTERN
            if status == FertilityStatus.BASIC_INFERTILE_PATTERN_ALTERNATE_EVENING:
                reasons = ["Basic Infertile Pattern established; alternate evening only."]
            else:
                reasons = ["Basic Infertile Pattern is not available on this day."]

        progress = _interpretation_progress(days[: index + 1], settings)
        feedback = _user_feedback(
            status=status,
            progress=progress,
            settings=settings,
            begins_this_evening=(
                status == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING
            ),
        )

        daily.append(
            DailyInterpretation(
                observation_date=observation_date,
                cycle_day=cycle_day,
                status=status,
                phase=phase,
                reasons=reasons,
                progress=progress,
                feedback=feedback,
            )
        )

    return daily


def _interpretation_progress(
    days: list[DailyObservation],
    settings: AppSettings,
) -> InterpretationProgress:
    today = days[-1]
    peak_day = _find_peak_day(days)
    temperature_count, temperature_required, temperature_confirmed = (
        _temperature_confirmation_progress(days, settings, peak_day)
    )
    mucus_count = _mucus_confirmation_progress(days)
    mucus_confirmed = mucus_count >= 3
    data_quality_messages: list[str] = []

    if today.waking_temperature is None:
        data_quality_messages.append("No waking temperature was recorded today.")
    elif today.temperature_disturbed:
        data_quality_messages.append(
            "Today's temperature is marked disturbed and is excluded from confirmation."
        )
    if today.fluid is None:
        data_quality_messages.append(
            "No mucus observation was recorded today; missing does not count as dry."
        )

    if today.waking_temperature is None:
        next_step = "Record a waking temperature before getting out of bed."
    elif today.fluid is None:
        next_step = "Record the most fertile mucus sign noticed today."
    elif not temperature_confirmed:
        if temperature_count:
            remaining = max(temperature_required - temperature_count, 1)
            next_step = (
                f"Continue BBT charting; {remaining} more qualifying elevated "
                f"temperature{'s' if remaining != 1 else ''} may be needed."
            )
        else:
            next_step = "Continue daily BBT charting to establish six low temperatures."
    elif not mucus_confirmed:
        remaining = 3 - mucus_count
        next_step = (
            f"Continue mucus charting; {remaining} more lower-quality or dry "
            f"day{'s' if remaining != 1 else ''} may be needed after Peak."
        )
    else:
        next_step = "Temperature and mucus double-checks are confirmed."

    return InterpretationProgress(
        temperature_high_count=temperature_count,
        temperature_high_required=temperature_required,
        temperature_confirmed=temperature_confirmed,
        mucus_lower_quality_count=min(mucus_count, 3),
        mucus_lower_quality_required=3,
        mucus_confirmed=mucus_confirmed,
        temperature_recorded_today=today.waking_temperature is not None,
        mucus_recorded_today=today.fluid is not None,
        data_quality_messages=data_quality_messages,
        next_step=next_step,
    )


def _mucus_confirmation_progress(days: list[DailyObservation]) -> int:
    last_peak_index: int | None = None
    for index, observation in enumerate(days):
        if _is_peak_quality_mucus(observation.fluid):
            last_peak_index = index

    if last_peak_index is None:
        return 0

    expected_date = days[last_peak_index].observation_date + timedelta(days=1)
    count = 0
    for observation in days[last_peak_index + 1 :]:
        if observation.observation_date != expected_date or observation.fluid is None:
            return 0
        expected_date += timedelta(days=1)
        if _is_peak_quality_mucus(observation.fluid):
            count = 0
        elif _is_lower_quality_or_dry(observation.fluid):
            count += 1
        else:
            count = 0
    return count


def _temperature_confirmation_progress(
    days: list[DailyObservation],
    settings: AppSettings,
    peak_day: date | None,
) -> tuple[int, int, bool]:
    require_fourth = peak_day is None
    shift = _find_temperature_shift(
        days,
        settings,
        peak_day=peak_day,
        require_fourth_for_unclear_mucus=require_fourth,
    )
    if shift:
        return len(shift.high_dates), len(shift.high_dates), True

    required = 4 if require_fourth else 3
    temps = [_temperature_celsius(observation, settings) for observation in days]
    best_count = 0

    for high_start in range(6, len(days)):
        high_start_date = days[high_start].observation_date
        if peak_day and high_start_date < peak_day + timedelta(days=1):
            continue
        if not _dates_are_consecutive(days, high_start - 6, 7):
            continue
        baseline = temps[high_start - 6 : high_start]
        if any(value is None for value in baseline):
            continue
        coverline = max(value for value in baseline if value is not None)
        count = 0
        for index in range(high_start, min(len(days), high_start + 4)):
            if index > high_start and days[index].observation_date != days[index - 1].observation_date + timedelta(days=1):
                break
            value = temps[index]
            if value is None or value <= coverline:
                break
            count += 1

        if high_start + count != len(days):
            continue
        if count >= 3 and not _meets_temperature_threshold(temps[high_start + 2], coverline):
            required = 4
        best_count = max(best_count, min(count, required))

    return best_count, required, False


def _user_feedback(
    *,
    status: FertilityStatus,
    progress: InterpretationProgress,
    settings: AppSettings,
    begins_this_evening: bool,
) -> UserFeedback:
    no_primary_signs = (
        not progress.temperature_recorded_today and not progress.mucus_recorded_today
    )

    if status in {
        FertilityStatus.ABSOLUTE_INFERTILITY,
        FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING,
    }:
        label = UserFertilityLabel.POST_OVULATION_CONFIRMED
        headline = "Post-ovulation phase confirmed"
        summary = (
            "Temperature and mucus double-checks confirm the post-ovulation phase"
            + (" beginning this evening." if begins_this_evening else ".")
        )
    elif no_primary_signs:
        label = UserFertilityLabel.NOT_ENOUGH_INFORMATION
        headline = "Not enough information"
        summary = "No temperature or mucus observation is available for today."
    elif status in {
        FertilityStatus.RELATIVE_INFERTILITY,
        FertilityStatus.BASIC_INFERTILE_PATTERN_ALTERNATE_EVENING,
    }:
        label = UserFertilityLabel.LOWER_PROBABILITY_METHOD_RULES_APPLY
        headline = "Lower probability — method rules apply"
        summary = (
            "A conservative Phase 1 or Basic Infertile Pattern rule applies; "
            "this is not a guarantee."
        )
    else:
        label = UserFertilityLabel.FERTILITY_POSSIBLE
        headline = "Fertility possible"
        summary = "The post-ovulation temperature and mucus double-check is not confirmed."

    return UserFeedback(
        label=label,
        headline=headline,
        summary=summary,
        action=_feedback_action(label, settings.tracking_goal),
    )


def _feedback_action(label: UserFertilityLabel, goal: TrackingGoal) -> str:
    if goal == TrackingGoal.AVOID_PREGNANCY:
        if label in {
            UserFertilityLabel.FERTILITY_POSSIBLE,
            UserFertilityLabel.NOT_ENOUGH_INFORMATION,
        }:
            return (
                "If avoiding pregnancy, treat today as potentially fertile and follow "
                "your chosen method."
            )
        if label == UserFertilityLabel.LOWER_PROBABILITY_METHOD_RULES_APPLY:
            return "Follow your method's Phase 1 or BIP instructions; lower probability is not zero."
        return "Apply your chosen method's post-ovulation instructions."

    if goal == TrackingGoal.ACHIEVE_PREGNANCY:
        if label == UserFertilityLabel.FERTILITY_POSSIBLE:
            return "If trying to conceive, this may be a fertile day."
        if label == UserFertilityLabel.POST_OVULATION_CONFIRMED:
            return "The fertile window appears closed for this cycle."
        return "Keep charting both signs to identify the fertile window."

    return "Keep recording temperature and the most fertile mucus sign each day."


def _bip_statuses(days: list[DailyObservation], settings: AppSettings) -> dict[date, FertilityStatus]:
    if not settings.bip_enabled and settings.rule_context != RuleContext.DELAYED_FERTILITY:
        return {}

    statuses: dict[date, FertilityStatus] = {}
    pattern: tuple[Any, ...] | None = None
    stable_count = 0
    active_start_index: int | None = None
    wait_until_index = 0

    for index, observation in enumerate(days):
        current = _bip_pattern(observation)
        changed = current is None or (pattern is not None and current != pattern)

        if pattern is None:
            pattern = current
            stable_count = 1 if current is not None else 0
        elif changed:
            pattern = current
            stable_count = 1 if current is not None else 0
            active_start_index = None
            wait_until_index = index + 4
        else:
            stable_count += 1

        if active_start_index is None and stable_count >= 21 and index >= wait_until_index:
            active_start_index = index

        if active_start_index is not None and not changed:
            if (index - active_start_index) % 2 == 0:
                statuses[observation.observation_date] = (
                    FertilityStatus.BASIC_INFERTILE_PATTERN_ALTERNATE_EVENING
                )
            else:
                statuses[observation.observation_date] = FertilityStatus.POTENTIALLY_FERTILE

    return statuses


def _bip_pattern(observation: DailyObservation) -> tuple[Any, ...] | None:
    if observation.bleeding != BleedingLevel.NONE:
        return None

    fluid = observation.fluid
    if fluid is None:
        return ("dry",)
    if _is_peak_quality_mucus(fluid):
        return None
    if _has_phase1_mucus_override(fluid):
        return (
            "mucus",
            fluid.sensation.value,
            fluid.quantity.value,
            fluid.color.value,
            fluid.texture.value,
            fluid.amount,
        )
    return ("dry",)


def _build_interpretation_cycles(
    observations: list[DailyObservation],
    settings: AppSettings,
) -> list[list[DailyObservation]]:
    if not observations:
        return []

    cycles: list[list[DailyObservation]] = []
    current: list[DailyObservation] = []
    previous: DailyObservation | None = None

    for observation in observations:
        new_menses = (
            observation.bleeding in _MENSES_START_LEVELS
            and previous is not None
            and previous.bleeding not in _MENSES_START_LEVELS
        )
        if new_menses and current and _has_any_temperature_shift(current, settings):
            cycles.append(current)
            current = [observation]
        else:
            current.append(observation)
        previous = observation

    if current:
        cycles.append(current)
    return cycles


def _has_any_temperature_shift(days: list[DailyObservation], settings: AppSettings) -> bool:
    return (
        _scan_temperature_shift(
            days,
            settings,
            earliest_first_high_date=None,
            latest_first_high_date=None,
            require_fourth=False,
        )
        is not None
    )


def _has_internal_menses_start(days: list[DailyObservation]) -> bool:
    previous: DailyObservation | None = None
    for index, observation in enumerate(days):
        new_menses = (
            index > 0
            and observation.bleeding in _MENSES_START_LEVELS
            and previous is not None
            and previous.bleeding not in _MENSES_START_LEVELS
        )
        if new_menses:
            return True
        previous = observation
    return False


def _apply_luteal_phase_warnings(cycles: list[CycleInterpretation]) -> None:
    completed: list[CycleInterpretation] = []
    for index, cycle in enumerate(cycles[:-1]):
        if cycle.temperature_shift is None:
            continue
        next_cycle = cycles[index + 1]
        cycle.luteal_phase_days = (
            next_cycle.start_date - cycle.temperature_shift.first_high_date
        ).days
        completed.append(cycle)

    short_recent = [cycle for cycle in completed[-3:] if (cycle.luteal_phase_days or 0) < 10]
    if len(short_recent) >= 2:
        for cycle in short_recent:
            cycle.warnings.append(
                InterpretationWarning(
                    code="short_luteal_phase",
                    message=(
                        "Luteal phase was under 10 days in at least two of the last "
                        "three completed ovulatory cycles."
                    ),
                    severity=WarningSeverity.CAUTION,
                    observation_date=cycle.end_date,
                )
            )


def _min_date(*values: date | None) -> date | None:
    actual = [item for item in values if item is not None]
    return min(actual) if actual else None


def _date_or_none(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def cycle_snapshot_from_interpretation(cycle: CycleInterpretation) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=cycle.cycle_index,
        start_date=cycle.start_date,
        end_date=cycle.end_date,
        span_days=cycle.span_days,
        logged_days=cycle.logged_days,
        starts_with_menses=cycle.starts_with_menses,
    )
