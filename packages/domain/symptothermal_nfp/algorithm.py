"""
Sensiplan double-check symptothermal algorithm.

Implements the Sensiplan method as specified in docs/SENSIPLAN_ALGORITHM_SPEC.md.
All temperature calculations are done in Celsius (the Sensiplan handbook unit).

Conservative principle: when any rule is ambiguous, unmet, or data is missing,
the day is FERTILE (S1), never infertile.

References in comments use "Spec §X" to cite the algorithm spec sections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import (
    AppSettings,
    DailyObservation,
    DayRuleTrace,
    EvaluationResult,
    PriorCycleSummary,
)
from .taxonomy import (
    BleedingLevel,
    FertilityState,
    FluidSensation,
    TemperatureUnit,
)

# Spec §4.1 step 3: 3rd high temp must be >= coverline + 0.2 °C
TEMP_THIRD_DAY_THRESHOLD_C = 0.2

# Spec §5: fever threshold
FEVER_THRESHOLD_C = 38.0

# Spec §4.2: number of dry days after peak for confirmation
PEAK_CONFIRM_DAYS_NORMAL = 3
PEAK_CONFIRM_DAYS_SLOW_RISE = 4  # Spec §4.2 step 3

# Mucus sensation ordinal mapping (higher = more fertile)
_SENSATION_ORDER = {
    FluidSensation.DRY: 0,
    FluidSensation.STICKY: 1,
    FluidSensation.CREAMY: 2,
    FluidSensation.WATERY: 3,
    FluidSensation.SLIPPERY: 4,
}


def _fahrenheit_to_celsius(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


# ---------------------------------------------------------------------------
# Stage 1: Temperature normalization
# ---------------------------------------------------------------------------

def _normalize_temps_to_celsius(
    observations: list[DailyObservation],
) -> list[float | None]:
    """
    Convert all temperatures to Celsius. Returns None for missing/invalid temps.
    Reads temperature_unit from each observation (Spec §1).
    """
    result: list[float | None] = []
    for obs in observations:
        if obs.waking_temperature is None:
            result.append(None)
            continue
        if obs.temperature_unit == TemperatureUnit.FAHRENHEIT:
            result.append(_fahrenheit_to_celsius(obs.waking_temperature))
        elif obs.temperature_unit == TemperatureUnit.CELSIUS:
            result.append(obs.waking_temperature)
        else:
            # Unknown unit with temp present -> invalid (conservative)
            result.append(None)
    return result


# ---------------------------------------------------------------------------
# Stage 2: Mucus quality mapping
# ---------------------------------------------------------------------------

def _compute_mucus_levels(
    observations: list[DailyObservation],
) -> tuple[list[int | None], int]:
    """
    Compute per-day mucus quality levels and the cycle's best quality level.

    Returns (levels, best_quality) where:
    - levels: per-day ordinal (0=dry..4=slippery), None if no observation
    - best_quality: highest quality observed in the cycle (for peak detection)

    Uses peak_quality flag if set by user; otherwise uses sensation ordinal.
    Spec §4.2: peak is per-user best quality, not hardcoded.
    """
    levels: list[int | None] = []
    best_quality = 0
    has_peak_quality_flag = False

    # First pass: check if any observation uses the peak_quality flag
    for obs in observations:
        if obs.fluid is not None and obs.fluid.peak_quality:
            has_peak_quality_flag = True
            break

    for obs in observations:
        if obs.fluid is None:
            levels.append(None)
            continue
        level = _SENSATION_ORDER.get(obs.fluid.sensation, 0)
        levels.append(level)

        if has_peak_quality_flag:
            # User explicitly marks peak quality days
            if obs.fluid.peak_quality and level > best_quality:
                best_quality = level
        else:
            if level > best_quality:
                best_quality = level

    return levels, best_quality


def _is_peak_quality(obs: DailyObservation, best_quality: int, has_peak_flag: bool) -> bool:
    """Check if a day's mucus is at peak quality level."""
    if obs.fluid is None:
        return False
    if has_peak_flag:
        return obs.fluid.peak_quality
    level = _SENSATION_ORDER.get(obs.fluid.sensation, 0)
    return level >= best_quality and best_quality > 0


# ---------------------------------------------------------------------------
# Stage 3: Disqualifier scan
# ---------------------------------------------------------------------------

@dataclass
class _DisqualifierResult:
    per_day_valid_temp: list[bool]
    cycle_disqualifiers: list[str]
    fever_detected: bool


def _scan_disqualifiers(
    temps_c: list[float | None],
    observations: list[DailyObservation],
) -> _DisqualifierResult:
    """
    Check for cycle-level disqualifiers (Spec §5).

    - Fever >= 38.0 °C
    - Disturbed temperatures
    - Missing temperatures (None)
    """
    n = len(observations)
    valid_temp = [False] * n
    disqualifiers: list[str] = []
    fever_detected = False

    for i in range(n):
        t = temps_c[i]
        obs = observations[i]

        if t is None:
            continue

        if obs.temperature_disturbed:
            # Disturbed temp is excluded from calculations but not a cycle disqualifier
            continue

        # Spec §5: fever >= 38.0 °C disqualifies
        if t >= FEVER_THRESHOLD_C:
            fever_detected = True
            disqualifiers.append(f"fever >= {FEVER_THRESHOLD_C} C on day {i + 1}")
            continue

        valid_temp[i] = True

    # Spec §5: < 3 valid mucus observations
    valid_mucus_count = sum(
        1 for obs in observations
        if obs.fluid is not None and obs.fluid.sensation != FluidSensation.DRY
    )
    if valid_mucus_count < 3:
        disqualifiers.append(f"fewer than 3 non-dry mucus observations ({valid_mucus_count})")

    return _DisqualifierResult(
        per_day_valid_temp=valid_temp,
        cycle_disqualifiers=disqualifiers,
        fever_detected=fever_detected,
    )


# ---------------------------------------------------------------------------
# Stage 4: Temperature shift (3-over-6 rule)
# ---------------------------------------------------------------------------

@dataclass
class _TempShiftResult:
    t_shift_day: int | None = None  # 1-indexed
    coverline_celsius: float | None = None
    confirmed_day: int | None = None  # 1-indexed, evening of
    slow_rise: bool = False
    drop_back: bool = False


def _find_temp_shift(
    temps_c: list[float | None],
    valid_temp: list[bool],
) -> _TempShiftResult:
    """
    Find temperature shift using 3-over-6 rule (Spec §4.1).

    For each candidate day:
    1. Find 6 preceding valid temps (skip invalid/disturbed/missing).
    2. Coverline = max of those 6.
    3. Check 3 consecutive days above coverline with day 3 >= coverline + 0.2°C.
    4. Exception 1 (slow rise): day 3 above but < +0.2°C -> need day 4 strictly above.
    5. Exception 2 (drop-back): one fallback allowed among highs, replaced by next day.
    """
    n = len(temps_c)

    for i in range(n):
        if not valid_temp[i]:
            continue

        # Find 6 preceding valid temps (Spec §4.1.1)
        preceding_valid: list[float] = []
        for j in range(i - 1, -1, -1):
            if valid_temp[j] and temps_c[j] is not None:
                preceding_valid.append(temps_c[j])
            if len(preceding_valid) == 6:
                break

        if len(preceding_valid) < 6:
            continue  # Spec §5: need 6 valid temps before candidate

        coverline = round(max(preceding_valid), 2)
        candidate = round(temps_c[i], 2)  # type: ignore[arg-type]

        # Spec §4.1 step 1: candidate must be strictly greater than coverline
        if candidate <= coverline:
            continue

        # Try to find 3 (or 4) consecutive highs starting at i
        result = _check_high_sequence(temps_c, valid_temp, i, coverline, n)
        if result is not None:
            return result

    return _TempShiftResult()


def _check_high_sequence(
    temps_c: list[float | None],
    valid_temp: list[bool],
    start_idx: int,
    coverline: float,
    n: int,
) -> _TempShiftResult | None:
    """
    Check if a sequence of high temps starting at start_idx satisfies the
    3-over-6 rule, including exceptions.
    """
    # Collect up to 5 consecutive days starting from start_idx
    # (3 normal + 1 possible drop-back replacement + 1 possible slow-rise day 4)
    high_indices: list[int] = []
    drop_back_used = False
    check_idx = start_idx

    # We need at least 3 qualifying highs (or 4 for slow-rise/drop-back)
    while check_idx < n and len(high_indices) < 5:
        if not valid_temp[check_idx] and check_idx != start_idx:
            # Spec §4.1 step 6: disturbed temps in high window are excluded
            # and treated like drop-back
            if not drop_back_used:
                drop_back_used = True
                check_idx += 1
                continue
            else:
                break  # More than one invalid -> cannot confirm here

        t = temps_c[check_idx]
        if t is None:
            if not drop_back_used:
                drop_back_used = True
                check_idx += 1
                continue
            else:
                break

        t_rounded = round(t, 2)

        if t_rounded > coverline:
            high_indices.append(check_idx)
        elif not drop_back_used:
            # Spec §4.1 step 5: one drop-back allowed
            drop_back_used = True
        else:
            break  # Second drop-back -> fail

        check_idx += 1

        # Check if we have enough highs for standard rule
        if len(high_indices) >= 3:
            # Check standard 3-over-6 (Spec §4.1 steps 1-3)
            day3_idx = high_indices[2]
            day3_t = round(temps_c[day3_idx], 2)  # type: ignore[arg-type]
            threshold = round(coverline + TEMP_THIRD_DAY_THRESHOLD_C, 2)

            if day3_t >= threshold:
                # Standard rule satisfied
                return _TempShiftResult(
                    t_shift_day=start_idx + 1,  # 1-indexed
                    coverline_celsius=coverline,
                    confirmed_day=day3_idx + 1,  # 1-indexed, evening of
                    slow_rise=False,
                    drop_back=drop_back_used,
                )

            # Spec §4.1 step 4: slow-rise exception
            # Day 3 is above coverline but < threshold. Need day 4 strictly above.
            if len(high_indices) >= 4:
                day4_idx = high_indices[3]
                day4_t = round(temps_c[day4_idx], 2)  # type: ignore[arg-type]
                # Spec §4.1 step 4: day 4 must be STRICTLY above coverline
                if day4_t > coverline:
                    return _TempShiftResult(
                        t_shift_day=start_idx + 1,
                        coverline_celsius=coverline,
                        confirmed_day=day4_idx + 1,
                        slow_rise=True,
                        drop_back=drop_back_used,
                    )
                else:
                    return None  # Day 4 failed

    # Check slow-rise with collected indices
    if len(high_indices) >= 4:
        day3_idx = high_indices[2]
        day3_t = round(temps_c[day3_idx], 2)  # type: ignore[arg-type]
        threshold = round(coverline + TEMP_THIRD_DAY_THRESHOLD_C, 2)

        if day3_t < threshold and day3_t > coverline:
            day4_idx = high_indices[3]
            day4_t = round(temps_c[day4_idx], 2)  # type: ignore[arg-type]
            if day4_t > coverline:
                return _TempShiftResult(
                    t_shift_day=start_idx + 1,
                    coverline_celsius=coverline,
                    confirmed_day=day4_idx + 1,
                    slow_rise=True,
                    drop_back=drop_back_used,
                )

    return None


# ---------------------------------------------------------------------------
# Stage 5: Peak day and mucus confirmation
# ---------------------------------------------------------------------------

@dataclass
class _PeakResult:
    peak_day: int | None = None  # 1-indexed
    confirmed_day: int | None = None  # 1-indexed, evening of


def _find_peak_and_confirm(
    mucus_levels: list[int | None],
    observations: list[DailyObservation],
    best_quality: int,
    has_peak_flag: bool,
    confirm_days: int = PEAK_CONFIRM_DAYS_NORMAL,
) -> _PeakResult:
    """
    Find peak day and confirm with dry days (Spec §4.2).

    Peak day = last day of best-quality mucus, identified retrospectively.
    Confirmation = confirm_days consecutive days of clearly drier pattern.
    """
    n = len(observations)
    if best_quality == 0:
        return _PeakResult()  # No fertile mucus observed

    # Find the LAST day of peak quality (Spec §4.2 step 1)
    # Peak is identified retrospectively: the last day before a sustained drying
    last_peak_idx: int | None = None

    for i in range(n):
        if _is_peak_quality(observations[i], best_quality, has_peak_flag):
            last_peak_idx = i

    if last_peak_idx is None:
        return _PeakResult()

    # Spec §4.2 step 2: check confirm_days of drier pattern after peak
    days_dry = 0
    for j in range(last_peak_idx + 1, n):
        if _is_peak_quality(observations[j], best_quality, has_peak_flag):
            # Not actually past peak yet — reset
            last_peak_idx = j
            days_dry = 0
            continue

        # Day is drier than peak
        days_dry += 1
        if days_dry >= confirm_days:
            return _PeakResult(
                peak_day=last_peak_idx + 1,  # 1-indexed
                confirmed_day=j + 1,  # 1-indexed, evening of this day
            )

    return _PeakResult(peak_day=last_peak_idx + 1)


# ---------------------------------------------------------------------------
# Stage 6: Pre-ovulatory infertility (v1 conservative MVP)
# ---------------------------------------------------------------------------

def _determine_pre_ov_last_safe_day(
    observations: list[DailyObservation],
    prior_cycles: list[PriorCycleSummary] | None,
) -> int:
    """
    Determine the last pre-ovulatory safe (S0) day.

    v1 Conservative MVP: no pre-ovulatory infertile days. All days are S1.
    Returns 0 (meaning no S0 days).

    Future versions will implement:
    - BIP deviation (Spec §3a)
    - Doering rule (Spec §3b) after 12+ prior cycles
    - First-cycle rule (Spec §3, first-cycle)
    - Menses safety (Spec §3, menses)
    """
    # v1: conservative — no pre-ov infertile days
    return 0


# ---------------------------------------------------------------------------
# Stage 7: State machine assembly
# ---------------------------------------------------------------------------

def _assemble_states(
    n: int,
    pre_ov_last_safe: int,
    temp_result: _TempShiftResult,
    peak_result: _PeakResult,
) -> tuple[list[FertilityState], int | None]:
    """
    Assemble per-day fertility states (Spec §2, §4.3).

    Returns (states, infertile_from_day) where infertile_from_day is 1-indexed.

    Evening-of semantics (Spec §4.3): the confirmation day itself is still
    fertile (S1). S2 starts the day AFTER the evening of the later confirmation.
    """
    if n == 0:
        return [], None

    states = [FertilityState.FERTILE] * n

    # v1 conservative: no S0 days (pre_ov_last_safe == 0)

    # Spec §4.3: both rules must be satisfied for S2
    infertile_from_day: int | None = None

    if temp_result.confirmed_day is not None and peak_result.confirmed_day is not None:
        # Evening of the later confirmation
        later_evening = max(temp_result.confirmed_day, peak_result.confirmed_day)
        # S2 starts the day AFTER that evening (Spec §4.3)
        infertile_from_day = later_evening + 1

        if infertile_from_day <= n:
            for i in range(infertile_from_day - 1, n):  # Convert to 0-indexed
                states[i] = FertilityState.POST_OV_INFERTILE

    return states, infertile_from_day


# ---------------------------------------------------------------------------
# Stage 8: Trace assembly
# ---------------------------------------------------------------------------

def _build_traces(
    observations: list[DailyObservation],
    temps_c: list[float | None],
    valid_temp: list[bool],
    mucus_levels: list[int | None],
    states: list[FertilityState],
    temp_result: _TempShiftResult,
    peak_result: _PeakResult,
    disqualifiers: list[str],
) -> list[DayRuleTrace]:
    """Build per-day rule traces for UI explanation."""
    traces: list[DayRuleTrace] = []

    for i, obs in enumerate(observations):
        day_num = i + 1
        state = states[i]
        rules: list[str] = []

        # State reason
        if state == FertilityState.POST_OV_INFERTILE:
            reason = "Post-ovulatory infertile (both temp and peak rules confirmed)"
        elif disqualifiers:
            reason = f"Fertile (cycle disqualified: {'; '.join(disqualifiers)})"
        else:
            reason = "Fertile (pre-ovulatory or awaiting confirmation)"

        # Temperature info
        temp_disq = None
        if obs.waking_temperature is not None and not valid_temp[i]:
            if obs.temperature_disturbed:
                temp_disq = "disturbed"
            elif temps_c[i] is not None and temps_c[i] >= FEVER_THRESHOLD_C:  # type: ignore[operator]
                temp_disq = "fever"
            elif obs.temperature_unit is None:
                temp_disq = "unknown unit"
            else:
                temp_disq = "excluded"

        # Rules applied
        if temp_result.t_shift_day is not None:
            shift_idx = temp_result.t_shift_day - 1
            if i == shift_idx:
                rules.append(f"1st high temp (coverline={temp_result.coverline_celsius:.2f}°C)")
            if temp_result.confirmed_day is not None and i == temp_result.confirmed_day - 1:
                label = "slow-rise " if temp_result.slow_rise else ""
                rules.append(f"temp rule confirmed ({label}3-over-6, evening)")
                if temp_result.drop_back:
                    rules.append("drop-back exception applied")

        if peak_result.peak_day is not None and i == peak_result.peak_day - 1:
            rules.append("peak day (last best-quality mucus)")
        if peak_result.confirmed_day is not None and i == peak_result.confirmed_day - 1:
            rules.append("peak rule confirmed (evening)")

        is_peak = peak_result.peak_day is not None and day_num == peak_result.peak_day

        traces.append(DayRuleTrace(
            cycle_day=day_num,
            observation_date=obs.observation_date,
            state=state,
            state_reason=reason,
            temp_celsius=round(temps_c[i], 2) if temps_c[i] is not None else None,
            temp_valid=valid_temp[i],
            temp_disqualify_reason=temp_disq,
            mucus_level=mucus_levels[i],
            is_peak_day=is_peak,
            rules_applied=rules,
        ))

    return traces


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def evaluate_cycle(
    observations: list[DailyObservation],
    settings: AppSettings | None = None,
    prior_cycles: list[PriorCycleSummary] | None = None,
) -> EvaluationResult:
    """
    Evaluate a cycle according to the Sensiplan double-check symptothermal method.

    All logic is performed in Celsius internally (Sensiplan handbook unit).

    Args:
        observations: Daily observations for the cycle, sorted by date.
        settings: App settings (temperature unit preference, etc.).
        prior_cycles: Summaries of prior cycles for Doering rule (unused in v1).

    Returns:
        EvaluationResult with per-day states, rule traces, and confirmation data.
    """
    if settings is None:
        settings = AppSettings()

    n = len(observations)
    if n == 0:
        return EvaluationResult(
            states=[],
            day_traces=[],
            t_shift_day=None,
            coverline_celsius=None,
            peak_day=None,
            temp_confirmed_day=None,
            peak_confirmed_day=None,
            infertile_from_day=None,
            disqualifiers=[],
            slow_rise_applied=False,
            drop_back_applied=False,
        )

    # Stage 1: Normalize temperatures to Celsius
    temps_c = _normalize_temps_to_celsius(observations)

    # Stage 2: Compute mucus levels
    mucus_levels, best_quality = _compute_mucus_levels(observations)
    has_peak_flag = any(
        obs.fluid is not None and obs.fluid.peak_quality
        for obs in observations
    )

    # Stage 3: Scan for disqualifiers
    disq = _scan_disqualifiers(temps_c, observations)

    # If cycle is disqualified, everything stays S1 (fertile)
    if disq.cycle_disqualifiers:
        states = [FertilityState.FERTILE] * n
        traces = _build_traces(
            observations, temps_c, disq.per_day_valid_temp,
            mucus_levels, states, _TempShiftResult(), _PeakResult(),
            disq.cycle_disqualifiers,
        )
        return EvaluationResult(
            states=states,
            day_traces=traces,
            t_shift_day=None,
            coverline_celsius=None,
            peak_day=None,
            temp_confirmed_day=None,
            peak_confirmed_day=None,
            infertile_from_day=None,
            disqualifiers=disq.cycle_disqualifiers,
            slow_rise_applied=False,
            drop_back_applied=False,
        )

    # Stage 4: Find temperature shift
    temp_result = _find_temp_shift(temps_c, disq.per_day_valid_temp)

    # Stage 5: Find peak day and confirm
    # Spec §4.2 step 3: slow-rise requires 4 dry days instead of 3
    confirm_days = (
        PEAK_CONFIRM_DAYS_SLOW_RISE if temp_result.slow_rise
        else PEAK_CONFIRM_DAYS_NORMAL
    )
    peak_result = _find_peak_and_confirm(
        mucus_levels, observations, best_quality, has_peak_flag, confirm_days,
    )

    # Stage 6: Pre-ovulatory infertility (v1: none)
    pre_ov_last_safe = _determine_pre_ov_last_safe_day(observations, prior_cycles)

    # Stage 7: Assemble states
    states, infertile_from_day = _assemble_states(
        n, pre_ov_last_safe, temp_result, peak_result,
    )

    # Stage 8: Build traces
    traces = _build_traces(
        observations, temps_c, disq.per_day_valid_temp,
        mucus_levels, states, temp_result, peak_result,
        disq.cycle_disqualifiers,
    )

    return EvaluationResult(
        states=states,
        day_traces=traces,
        t_shift_day=temp_result.t_shift_day,
        coverline_celsius=temp_result.coverline_celsius,
        peak_day=peak_result.peak_day,
        temp_confirmed_day=temp_result.confirmed_day,
        peak_confirmed_day=peak_result.confirmed_day,
        infertile_from_day=infertile_from_day,
        disqualifiers=disq.cycle_disqualifiers,
        slow_rise_applied=temp_result.slow_rise,
        drop_back_applied=temp_result.drop_back,
    )
