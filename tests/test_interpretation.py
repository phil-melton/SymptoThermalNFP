import datetime as dt

from symptothermal_nfp.interpretation import (
    FertilityStatus,
    UserFertilityLabel,
    evaluate_observations,
)
from symptothermal_nfp.models import AppSettings, DailyObservation, FluidObservation
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    RuleContext,
    TemperatureUnit,
    TrackingGoal,
)


def test_standard_double_check_confirms_phase_3_from_evening() -> None:
    start = dt.date(2026, 4, 1)
    observations = _stm_cycle(start, length=12, shift_day=7)

    report = evaluate_observations(observations)
    cycle = report.cycles[0]

    assert cycle.peak_day == start + dt.timedelta(days=5)
    assert cycle.mucus_confirmation_date == start + dt.timedelta(days=8)
    assert cycle.temperature_shift is not None
    assert cycle.temperature_shift.first_high_date == start + dt.timedelta(days=6)
    assert cycle.temperature_shift.confirmed_date == start + dt.timedelta(days=8)
    assert cycle.absolute_infertility_start_date == start + dt.timedelta(days=8)
    assert cycle.days[8].status == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING
    assert cycle.days[9].status == FertilityStatus.ABSOLUTE_INFERTILITY


def test_mucus_confirmation_waits_for_third_consecutive_lower_quality_day_after_peak() -> None:
    start = dt.date(2026, 4, 1)
    observations = [
        _observation(
            start,
            day,
            temp=36.4,
            fluid=_peak() if day == 6 else _sticky() if day in {7, 8} else _dry(),
            bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
        )
        for day in range(1, 9)
    ]

    report = evaluate_observations(observations)
    cycle = report.cycles[0]

    assert cycle.peak_day == start + dt.timedelta(days=5)
    assert cycle.mucus_confirmation_date is None
    assert cycle.absolute_infertility_start_date is None


def test_missing_post_peak_calendar_day_prevents_mucus_confirmation() -> None:
    start = dt.date(2026, 4, 1)
    temperatures_by_day = {
        1: 36.40,
        2: 36.42,
        3: 36.41,
        4: 36.43,
        5: 36.42,
        6: 36.44,
        8: 36.40,
        9: 36.42,
        10: 36.41,
        11: 36.43,
        12: 36.42,
        13: 36.44,
        14: 36.70,
        15: 36.73,
        16: 36.80,
    }
    observations = [
        _observation(
            start,
            day,
            temp=temp,
            fluid=_peak() if day == 6 else _sticky() if day > 6 else _dry(),
            bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
        )
        for day, temp in temperatures_by_day.items()
    ]

    report = evaluate_observations(observations)
    cycle = report.cycles[0]

    assert cycle.peak_day == start + dt.timedelta(days=5)
    assert cycle.mucus_confirmation_date is None
    assert cycle.temperature_shift is not None
    assert cycle.temperature_shift.confirmed_date == start + dt.timedelta(days=15)
    assert cycle.absolute_infertility_start_date is None
    assert cycle.days[-1].status == FertilityStatus.POTENTIALLY_FERTILE


def test_renewed_peak_quality_mucus_moves_peak_day_and_restarts_countdown() -> None:
    start = dt.date(2026, 4, 1)
    temperatures = [
        36.40,
        36.42,
        36.43,
        36.41,
        36.44,
        36.45,
        36.46,
        36.45,
        36.75,
        36.78,
        36.82,
    ]
    observations = []
    for day, temp in enumerate(temperatures, start=1):
        if day in {6, 8}:
            fluid = _peak()
        elif day in {7, 9, 10, 11}:
            fluid = _sticky()
        else:
            fluid = _dry()
        observations.append(
            _observation(
                start,
                day,
                temp=temp,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )

    report = evaluate_observations(observations)
    cycle = report.cycles[0]

    assert cycle.peak_day == start + dt.timedelta(days=7)
    assert cycle.mucus_confirmation_date == start + dt.timedelta(days=10)
    assert cycle.temperature_shift is not None
    assert cycle.temperature_shift.confirmed_date == start + dt.timedelta(days=10)
    assert cycle.absolute_infertility_start_date == start + dt.timedelta(days=10)
    assert cycle.days[10].status == FertilityStatus.ABSOLUTE_INFERTILITY_FROM_EVENING


def test_fourth_day_temperature_exception_confirms_on_fourth_high() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.45, 36.44, 36.46, 36.43, 36.50, 36.56, 36.57, 36.61, 36.55],
    )

    report = evaluate_observations(observations)
    shift = report.cycles[0].temperature_shift

    assert shift is not None
    assert shift.confirmed_date == start + dt.timedelta(days=9)
    assert shift.fourth_day_exception is True
    assert report.cycles[0].absolute_infertility_start_date == start + dt.timedelta(days=9)


def test_third_high_exactly_at_celsius_threshold_confirms_without_fourth_day() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.43, 36.41, 36.45, 36.42, 36.46, 36.47, 36.50, 36.66],
    )

    report = evaluate_observations(observations)
    shift = report.cycles[0].temperature_shift

    assert shift is not None
    assert shift.coverline_celsius == 36.46
    assert shift.confirmed_date == start + dt.timedelta(days=8)
    assert shift.threshold_met_on_third is True
    assert shift.fourth_day_exception is False


def test_third_high_below_threshold_without_fourth_day_does_not_confirm() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.43, 36.41, 36.45, 36.42, 36.46, 36.47, 36.50, 36.65],
    )

    report = evaluate_observations(observations)

    assert report.cycles[0].temperature_shift is None
    assert report.cycles[0].absolute_infertility_start_date is None


def test_temperature_equal_to_coverline_is_not_counted_as_high() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.43, 36.41, 36.45, 36.42, 36.46, 36.46, 36.70, 36.75, 36.76],
    )

    report = evaluate_observations(observations)
    shift = report.cycles[0].temperature_shift

    assert shift is not None
    assert shift.first_high_date == start + dt.timedelta(days=7)
    assert shift.baseline_dates == [
        start + dt.timedelta(days=offset)
        for offset in range(1, 7)
    ]


def test_missing_calendar_day_prevents_temperature_confirmation() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.43, 36.41, 36.45, 36.42, 36.46, 36.70, 36.73, 36.80, 36.82],
    )
    observations = [
        observation
        for observation in observations
        if observation.observation_date != start + dt.timedelta(days=3)
    ]

    report = evaluate_observations(observations)

    assert report.cycles[0].temperature_shift is None
    assert report.cycles[0].absolute_infertility_start_date is None


def test_disturbed_baseline_temperature_blocks_shift_confirmation() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.43, 36.41, 36.45, 36.42, 36.46, 36.70, 36.73, 36.80],
        disturbed_days={3},
    )

    report = evaluate_observations(observations)

    assert report.cycles[0].temperature_shift is None
    assert report.cycles[0].absolute_infertility_start_date is None


def test_disturbed_temperature_breaks_shift_confirmation() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [36.40, 36.45, 36.44, 36.46, 36.43, 36.50, 36.70, 36.72, 36.80, 36.82],
        disturbed_days={8},
    )

    report = evaluate_observations(observations)

    assert report.cycles[0].temperature_shift is None
    assert report.cycles[0].absolute_infertility_start_date is None


def test_fahrenheit_temperatures_are_normalized_for_shift_detection() -> None:
    start = dt.date(2026, 4, 1)
    observations = _custom_temperature_cycle(
        start,
        [97.5, 97.6, 97.55, 97.58, 97.52, 97.60, 98.10, 98.20, 98.40],
        unit=TemperatureUnit.FAHRENHEIT,
    )

    report = evaluate_observations(observations, AppSettings(temperature_unit=TemperatureUnit.FAHRENHEIT))
    shift = report.cycles[0].temperature_shift

    assert shift is not None
    assert shift.confirmed_date == start + dt.timedelta(days=8)
    assert shift.coverline_celsius < 37.0


def test_premature_temperature_rise_is_ignored_until_after_peak_day() -> None:
    start = dt.date(2026, 4, 1)
    observations: list[DailyObservation] = []
    temps = [36.40, 36.45, 36.44, 36.46, 36.43, 36.50, 36.70, 36.72, 36.90, 36.91, 37.00]
    for day, temp in enumerate(temps, start=1):
        if day == 8:
            fluid = _peak()
        elif day in {9, 10, 11}:
            fluid = _sticky()
        else:
            fluid = _dry()
        observations.append(
            _observation(
                start,
                day,
                temp=temp,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )

    report = evaluate_observations(observations)
    shift = report.cycles[0].temperature_shift

    assert shift is not None
    assert shift.first_high_date == start + dt.timedelta(days=8)
    assert shift.confirmed_date == start + dt.timedelta(days=10)
    assert shift.premature_rise_ignored is True


def test_phase1_history_rules_use_conservative_calendar_boundaries() -> None:
    cases = [
        (0, 28, 1),
        (4, 28, 6),
        (7, 28, 8),
        (13, 28, 9),
    ]

    for previous_count, previous_length, expected_fertile_day in cases:
        observations, current_start = _history_with_current(previous_count, previous_length=previous_length)
        report = evaluate_observations(observations)
        current = report.cycles[-1]

        assert current.fertile_window_start_date == current_start + dt.timedelta(days=expected_fertile_day - 1)
        if expected_fertile_day > 1:
            assert current.days[expected_fertile_day - 2].status == FertilityStatus.RELATIVE_INFERTILITY
        assert current.days[expected_fertile_day - 1].status == FertilityStatus.POTENTIALLY_FERTILE


def test_optional_doering_rule_shortens_phase1_when_enabled() -> None:
    observations, current_start = _history_with_current(13, previous_length=28, shift_day=13)

    report = evaluate_observations(observations, AppSettings(use_doering_rule=True))

    assert report.cycles[-1].fertile_window_start_date == current_start + dt.timedelta(days=7)


def test_optional_rotzer_rule_allows_first_six_days_when_enabled() -> None:
    observations, current_start = _history_with_current(4, previous_length=26, shift_day=8)

    report = evaluate_observations(observations, AppSettings(use_rotzer_rule=True))

    assert report.cycles[-1].fertile_window_start_date == current_start + dt.timedelta(days=6)


def test_basic_infertile_pattern_uses_alternate_evenings_after_21_stable_days() -> None:
    start = dt.date(2026, 4, 1)
    observations = [_observation(start, day, fluid=_dry()) for day in range(1, 23)]

    report = evaluate_observations(
        observations,
        AppSettings(rule_context=RuleContext.DELAYED_FERTILITY),
    )

    assert report.cycles[0].days[20].status == FertilityStatus.BASIC_INFERTILE_PATTERN_ALTERNATE_EVENING
    assert report.cycles[0].days[21].status == FertilityStatus.POTENTIALLY_FERTILE


def test_bleeding_without_shift_is_treated_as_possible_anovulatory_bleeding() -> None:
    start = dt.date(2026, 4, 1)
    observations = [
        _observation(start, day, temp=36.4, fluid=_dry(), bleeding=BleedingLevel.MEDIUM if day in {1, 10} else BleedingLevel.NONE)
        for day in range(1, 13)
    ]

    report = evaluate_observations(observations)

    assert len(report.cycles) == 1
    assert any(warning.code == "possible_anovulatory_bleeding" for warning in report.cycles[0].warnings)


def test_short_luteal_phase_warning_requires_two_of_three_recent_cycles() -> None:
    start = dt.date(2026, 4, 1)
    observations: list[DailyObservation] = []
    cycle_start = start
    for _ in range(4):
        observations.extend(_stm_cycle(cycle_start, length=16, shift_day=10))
        cycle_start += dt.timedelta(days=16)

    report = evaluate_observations(observations)

    warned_cycles = [
        cycle for cycle in report.cycles if any(warning.code == "short_luteal_phase" for warning in cycle.warnings)
    ]
    assert len(warned_cycles) >= 2


def test_interpretation_report_serializes_as_json_contract() -> None:
    report = evaluate_observations(_stm_cycle(dt.date(2026, 4, 1), length=12, shift_day=7))

    payload = report.as_dict()

    assert payload["rule_pack_version"] == "stm-v1"
    assert payload["cycles"][0]["temperature_shift"]["confirmed_date"] == "2026-04-09"
    assert payload["cycles"][0]["days"][0]["status"] == "potentially_fertile"
    assert payload["cycles"][0]["days"][0]["feedback"]["headline"] == "Fertility possible"
    assert payload["cycles"][0]["days"][0]["progress"]["mucus_lower_quality_required"] == 3


def test_missing_mucus_does_not_count_as_dry_in_peak_countdown() -> None:
    observations = _stm_cycle(dt.date(2026, 4, 1), length=12, shift_day=7)
    observations[6].fluid = None

    report = evaluate_observations(observations)
    cycle = report.cycles[0]

    assert cycle.mucus_confirmation_date is None
    assert cycle.absolute_infertility_start_date is None
    assert cycle.days[-1].progress is not None
    assert cycle.days[-1].progress.mucus_confirmed is False


def test_feedback_uses_plain_language_and_tracking_goal() -> None:
    start = dt.date(2026, 4, 1)
    no_signs = evaluate_observations([DailyObservation(observation_date=start)])
    incomplete = no_signs.cycles[0].days[0].feedback

    avoid = evaluate_observations(
        [DailyObservation(observation_date=start, fluid=_dry())],
        AppSettings(tracking_goal=TrackingGoal.AVOID_PREGNANCY),
    ).cycles[0].days[0].feedback

    assert incomplete is not None
    assert incomplete.label == UserFertilityLabel.NOT_ENOUGH_INFORMATION
    assert avoid is not None
    assert avoid.label == UserFertilityLabel.FERTILITY_POSSIBLE
    assert "treat today as potentially fertile" in avoid.action


def test_confirmed_day_feedback_says_post_ovulation_not_absolute_infertility() -> None:
    report = evaluate_observations(_stm_cycle(dt.date(2026, 4, 1), length=12, shift_day=7))
    confirmed = report.cycles[0].days[8].feedback

    assert confirmed is not None
    assert confirmed.label == UserFertilityLabel.POST_OVULATION_CONFIRMED
    assert confirmed.headline == "Post-ovulation phase confirmed"


def _history_with_current(
    previous_count: int,
    *,
    previous_length: int,
    shift_day: int = 8,
) -> tuple[list[DailyObservation], dt.date]:
    start = dt.date(2026, 1, 1)
    observations: list[DailyObservation] = []
    cycle_start = start
    for _ in range(previous_count):
        observations.extend(_stm_cycle(cycle_start, length=previous_length, shift_day=shift_day))
        cycle_start += dt.timedelta(days=previous_length)

    current_start = cycle_start
    for day in range(1, 11):
        observations.append(
            _observation(
                current_start,
                day,
                temp=36.4,
                fluid=_dry(),
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations, current_start


def _stm_cycle(start: dt.date, *, length: int, shift_day: int) -> list[DailyObservation]:
    observations: list[DailyObservation] = []
    for day in range(1, length + 1):
        if day < shift_day:
            temp = 36.40 + ((day % 5) * 0.02)
        elif day < shift_day + 3:
            temp = 36.75 + ((day - shift_day) * 0.03)
        else:
            temp = 36.80

        if day == shift_day - 1:
            fluid = _peak()
        elif shift_day <= day <= shift_day + 2:
            fluid = _sticky()
        else:
            fluid = _dry()

        observations.append(
            _observation(
                start,
                day,
                temp=temp,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations


def _custom_temperature_cycle(
    start: dt.date,
    temperatures: list[float],
    *,
    disturbed_days: set[int] | None = None,
    unit: TemperatureUnit | None = None,
) -> list[DailyObservation]:
    disturbed_days = disturbed_days or set()
    observations: list[DailyObservation] = []
    for day, temp in enumerate(temperatures, start=1):
        if day == 6:
            fluid = _peak()
        elif day >= 7:
            fluid = _sticky()
        else:
            fluid = _dry()
        observations.append(
            _observation(
                start,
                day,
                temp=temp,
                unit=unit,
                disturbed=day in disturbed_days,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations


def _observation(
    start: dt.date,
    cycle_day: int,
    *,
    temp: float | None = None,
    unit: TemperatureUnit | None = None,
    disturbed: bool = False,
    fluid: FluidObservation | None = None,
    bleeding: BleedingLevel = BleedingLevel.NONE,
) -> DailyObservation:
    return DailyObservation(
        observation_date=start + dt.timedelta(days=cycle_day - 1),
        waking_temperature=temp,
        temperature_unit=unit,
        temperature_disturbed=disturbed,
        fluid=fluid,
        bleeding=bleeding,
    )


def _dry() -> FluidObservation:
    return FluidObservation(sensation=FluidSensation.DRY, quantity=FluidQuantity.NONE)


def _sticky() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.STICKY,
        quantity=FluidQuantity.LOW,
        color=MucusColor.CLOUDY,
        texture=MucusTexture.STICKY,
        amount=1,
    )


def _peak() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.SLIPPERY,
        quantity=FluidQuantity.HIGH,
        color=MucusColor.CLEAR,
        texture=MucusTexture.STRETCHY,
        amount=5,
        peak_quality=True,
    )
