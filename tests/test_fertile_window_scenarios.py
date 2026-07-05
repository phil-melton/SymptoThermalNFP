"""Robust fertile-day determination scenarios for the symptothermal method.

Each test scripts a full cycle of observations and asserts the day-by-day
fertility statuses the conservative rule pack must produce.
"""

from __future__ import annotations

import datetime as dt

from cycle_builders import dry, observation, peak, repeated_textbook_cycles, sticky, textbook_cycle, watery
from symptothermal_nfp.interpretation import FertilityStatus, evaluate_observations
from symptothermal_nfp.models import AppSettings
from symptothermal_nfp.taxonomy import BleedingLevel, TemperatureUnit

START = dt.date(2026, 3, 1)


def _statuses(cycle) -> dict[int, FertilityStatus]:
    return {day.cycle_day: day.status for day in cycle.days}


def test_textbook_cycle_day_by_day_statuses() -> None:
    report = evaluate_observations(textbook_cycle(START))
    cycle = report.cycles[0]
    statuses = _statuses(cycle)

    assert cycle.peak_day == START + dt.timedelta(days=13)  # day 14
    assert cycle.mucus_confirmation_date == START + dt.timedelta(days=16)  # day 17
    assert cycle.temperature_shift is not None
    assert cycle.temperature_shift.first_high_date == START + dt.timedelta(days=14)
    assert cycle.temperature_shift.confirmed_date == START + dt.timedelta(days=16)
    assert abs(cycle.temperature_shift.coverline_celsius - 36.45) < 1e-9
    assert cycle.temperature_shift.threshold_met_on_third
    assert cycle.absolute_infertility_start_date == START + dt.timedelta(days=16)

    # With no cycle history, every pre-confirmation day is treated as fertile.
    for day in range(1, 17):
        assert statuses[day] == FertilityStatus.POTENTIALLY_FERTILE, f"day {day}"
    assert statuses[17] == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING
    for day in range(18, 29):
        assert statuses[day] == FertilityStatus.ABSOLUTE_INFERTILITY, f"day {day}"


def test_fahrenheit_temperatures_give_identical_interpretation() -> None:
    celsius = evaluate_observations(textbook_cycle(START, unit=TemperatureUnit.CELSIUS))
    fahrenheit = evaluate_observations(
        textbook_cycle(START, unit=TemperatureUnit.FAHRENHEIT),
        AppSettings(temperature_unit=TemperatureUnit.FAHRENHEIT),
    )

    c_cycle, f_cycle = celsius.cycles[0], fahrenheit.cycles[0]
    assert f_cycle.peak_day == c_cycle.peak_day
    assert f_cycle.temperature_shift is not None
    assert f_cycle.temperature_shift.first_high_date == c_cycle.temperature_shift.first_high_date
    assert f_cycle.temperature_shift.confirmed_date == c_cycle.temperature_shift.confirmed_date
    assert f_cycle.absolute_infertility_start_date == c_cycle.absolute_infertility_start_date
    assert _statuses(f_cycle) == _statuses(c_cycle)


def test_disturbed_first_high_temperature_blocks_confirmation() -> None:
    baseline = evaluate_observations(textbook_cycle(START))
    disturbed = evaluate_observations(textbook_cycle(START, disturbed_days={15}))

    assert baseline.cycles[0].absolute_infertility_start_date is not None
    cycle = disturbed.cycles[0]

    # The disturbed reading is excluded, so this cycle can no longer produce a
    # valid 6-baseline + 3-high window and must stay fertile to the end.
    assert cycle.temperature_shift is None
    assert cycle.absolute_infertility_start_date is None
    statuses = _statuses(cycle)
    for day in range(15, 29):
        assert statuses[day] == FertilityStatus.POTENTIALLY_FERTILE, f"day {day}"


def test_fourth_day_exception_when_third_high_misses_threshold() -> None:
    observations = []
    for day in range(1, 22):
        if day <= 3:
            fluid, bleeding = None, BleedingLevel.MEDIUM
        elif day <= 10:
            fluid, bleeding = dry(), BleedingLevel.NONE
        elif day <= 13:
            fluid, bleeding = watery(), BleedingLevel.NONE
        elif day == 14:
            fluid, bleeding = peak(), BleedingLevel.NONE
        else:
            fluid, bleeding = sticky(), BleedingLevel.NONE

        temp = {15: 36.55, 16: 36.60, 17: 36.55, 18: 36.65}.get(day, 36.40 if day <= 14 else 36.62)
        observations.append(observation(START, day, temp=temp, fluid=fluid, bleeding=bleeding))

    cycle = evaluate_observations(observations).cycles[0]

    assert cycle.temperature_shift is not None
    assert abs(cycle.temperature_shift.coverline_celsius - 36.40) < 1e-9
    assert not cycle.temperature_shift.threshold_met_on_third
    assert cycle.temperature_shift.fourth_day_exception
    assert cycle.temperature_shift.confirmed_date == START + dt.timedelta(days=17)  # day 18
    assert cycle.mucus_confirmation_date == START + dt.timedelta(days=16)  # day 17
    # Double-check waits for the later of the two confirmations (day 18).
    assert cycle.absolute_infertility_start_date == START + dt.timedelta(days=17)
    statuses = _statuses(cycle)
    assert statuses[17] == FertilityStatus.POTENTIALLY_FERTILE
    assert statuses[18] == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING
    assert statuses[19] == FertilityStatus.ABSOLUTE_INFERTILITY


def test_unclear_mucus_requires_fourth_high_and_never_unlocks_phase_3() -> None:
    observations = []
    for day in range(1, 22):
        fluid = None if day <= 3 else dry()
        bleeding = BleedingLevel.MEDIUM if day <= 3 else BleedingLevel.NONE
        temp = {15: 36.65, 16: 36.70, 17: 36.75, 18: 36.72}.get(day, 36.40 if day <= 14 else 36.71)
        observations.append(observation(START, day, temp=temp, fluid=fluid, bleeding=bleeding))

    cycle = evaluate_observations(observations).cycles[0]

    assert cycle.peak_day is None
    assert cycle.temperature_shift is not None
    assert cycle.temperature_shift.unclear_mucus_exception
    # Fourth elevated day required: confirmation lands on day 18, not day 17.
    assert cycle.temperature_shift.confirmed_date == START + dt.timedelta(days=17)
    assert any(warning.code == "unclear_mucus_peak" for warning in cycle.warnings)
    # Without a mucus double-check the conservative pack never declares Phase 3.
    assert cycle.absolute_infertility_start_date is None
    assert all(day.status == FertilityStatus.POTENTIALLY_FERTILE for day in cycle.days)


def test_anovulatory_cycle_stays_fertile_throughout() -> None:
    observations = []
    for day in range(1, 29):
        fluid = None if day <= 3 else sticky() if day % 3 == 0 else dry()
        bleeding = BleedingLevel.MEDIUM if day <= 3 else BleedingLevel.NONE
        temp = 36.40 + (0.03 if day % 2 == 0 else 0.0)  # flat, no shift
        observations.append(observation(START, day, temp=temp, fluid=fluid, bleeding=bleeding))

    cycle = evaluate_observations(observations).cycles[0]

    assert cycle.temperature_shift is None
    assert cycle.absolute_infertility_start_date is None
    assert all(day.status == FertilityStatus.POTENTIALLY_FERTILE for day in cycle.days)


def test_premature_rise_before_peak_day_is_ignored() -> None:
    temps = {10: 36.70, 11: 36.72, 12: 36.75, 17: 36.80, 18: 36.85, 19: 36.95}
    observations = []
    for day in range(1, 25):
        if day <= 3:
            fluid, bleeding = None, BleedingLevel.MEDIUM
        elif day in {14, 15}:
            fluid, bleeding = watery(), BleedingLevel.NONE
        elif day == 16:
            fluid, bleeding = peak(), BleedingLevel.NONE
        else:
            fluid, bleeding = dry(), BleedingLevel.NONE
        temp = temps.get(day, 36.42 if day <= 16 else 36.90)
        observations.append(observation(START, day, temp=temp, fluid=fluid, bleeding=bleeding))

    cycle = evaluate_observations(observations).cycles[0]

    assert cycle.peak_day == START + dt.timedelta(days=15)  # day 16
    assert cycle.temperature_shift is not None
    assert cycle.temperature_shift.premature_rise_ignored
    # Highs are only counted after Peak Day; first high is day 17.
    assert cycle.temperature_shift.first_high_date == START + dt.timedelta(days=16)
    assert cycle.temperature_shift.confirmed_date == START + dt.timedelta(days=18)  # day 19
    assert cycle.mucus_confirmation_date == START + dt.timedelta(days=18)
    assert cycle.absolute_infertility_start_date == START + dt.timedelta(days=18)
    statuses = _statuses(cycle)
    # The pre-Peak rise must never have opened Phase 3.
    for day in range(10, 19):
        assert statuses[day] == FertilityStatus.POTENTIALLY_FERTILE, f"day {day}"
    assert statuses[19] == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING


def test_calendar_rule_grants_phase_1_after_four_cycles_of_history() -> None:
    observations = repeated_textbook_cycles(START, 5)
    report = evaluate_observations(observations)

    assert len(report.cycles) == 5
    fifth = report.cycles[4]
    statuses = _statuses(fifth)

    # Shortest of four 28-day cycles: S minus 21 capped at day 5 for 4-6 cycles
    # of history, so days 1-5 are relatively infertile and day 6 opens the window.
    assert fifth.fertile_window_start_date == fifth.start_date + dt.timedelta(days=5)
    for day in range(1, 6):
        assert statuses[day] == FertilityStatus.RELATIVE_INFERTILITY, f"day {day}"
    assert statuses[6] == FertilityStatus.POTENTIALLY_FERTILE
    assert statuses[17] == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING
    assert statuses[18] == FertilityStatus.ABSOLUTE_INFERTILITY

    # And the first cycle (no history) must NOT have had a Phase 1.
    first_statuses = _statuses(report.cycles[0])
    assert first_statuses[1] == FertilityStatus.POTENTIALLY_FERTILE
    assert any(
        warning.code == "insufficient_cycle_history" for warning in report.cycles[0].warnings
    )


def test_early_mucus_overrides_calendar_phase_1() -> None:
    observations = repeated_textbook_cycles(START, 4)
    fifth_start = START + dt.timedelta(days=4 * 28)
    fifth = textbook_cycle(fifth_start)
    # Peak-quality mucus already on day 3 must end Phase 1 immediately.
    fifth[2] = observation(
        fifth_start, 3, temp=36.40, fluid=watery(), bleeding=BleedingLevel.MEDIUM
    )
    report = evaluate_observations(observations + fifth)

    cycle = report.cycles[4]
    statuses = _statuses(cycle)
    assert cycle.fertile_window_start_date == fifth_start + dt.timedelta(days=2)
    assert statuses[1] == FertilityStatus.RELATIVE_INFERTILITY
    assert statuses[2] == FertilityStatus.RELATIVE_INFERTILITY
    assert statuses[3] == FertilityStatus.POTENTIALLY_FERTILE
